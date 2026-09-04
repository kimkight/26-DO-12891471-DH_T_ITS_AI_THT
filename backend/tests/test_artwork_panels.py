"""A filing whose labels are embedded as separate panels (#121, OQ-24, ADR 0010).

The author put a second real filed COLA, a bourbon, through the deployed
v1.4.0 build on 2026-09-03. One of five checks passed. The reader never saw the
label: of six embedded pictures, five were rejected before any was read, every
one of them on ``short_edge``, and the aspect-ratio rule would have rejected
four of them next. Measured on that build, the pictures were:

======  ==========  =========  ==============  ======
page    size        area       ratio           verdict at v1.4.0
======  ==========  =========  ==============  ======
2       1103 x 340  375,020    3.24            rejected, short_edge
2       772 x 194   149,768    3.98            rejected, short_edge
3       1050 x 309  324,450    3.40            rejected, short_edge
3       187 x 1697  317,339    9.07            rejected, short_edge
4       1350 x 300  405,000    4.50            rejected, short_edge
======  ==========  =========  ==============  ======

Those are a front label, a back label, a wrap-around and a vertical side band.
The signature on the author's other filing is 687 by 195, which is 133,965
pixels. Area alone puts the signature on one side and four of the five panels
on the other; the short edge and the ratio put every panel on the signature's
side. The two shape rules were set from one document whose artwork is a single
1750 by 1150 sheet, and they are gone.

This fixture is that filing's shape with synthetic text: a 1350 by 300 front
panel carrying the brand and the class or type, a 1050 by 309 back panel
carrying the alcohol content, the net contents and the government warning, a
187 by 1697 side band, and a 687 by 195 signature. Neither of the author's
documents is in the repository; only the dimensions are. Before the change
this document returned ``no_label_to_check``; after it, all five checks pass
and the signature is still excluded. It is the regression test OQ-24 asked for.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.formmaker import (  # noqa: E402
    ApplicationSpec,
    as_pdf_bytes,
    paper_form_lines,
    registry_printout_lines,
)
from samples.labelmaker import PanelSpec, render_panel_png_bytes  # noqa: E402

from app.application_form import _rejection, parse_application_document  # noqa: E402
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.warning import WARNING_STATEMENT  # noqa: E402
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402
from tests.test_embedded_artwork import signature_strip  # noqa: E402

client = TestClient(app)

# The bourbon filing's pictures, as measured on the deployed v1.4.0 build.
BOURBON_PICTURES = ((1103, 340), (772, 194), (1050, 309), (187, 1697), (1350, 300))
# The Registry printout's pictures, as measured on v1.2.0 (#121).
REGISTRY_PICTURES = (
    (1442, 433),
    (754, 379),
    (800, 226),
    (519, 327),
    (190, 190),
    (355, 93),
    (238, 62),
)
# The applicant's signature on the author's own filing.
SIGNATURE = (687, 195)

FRONT = PanelSpec(1350, 300, ("STONE'S THROW", "Kentucky Straight Bourbon Whiskey"))
BACK = PanelSpec(1050, 309, ("45% Alc./Vol. (90 Proof)", "750 mL", WARNING_STATEMENT))
SIDE = PanelSpec(
    187, 1697, ("Distilled and bottled by Example Distilling Company, Anytown",), vertical=True
)


def bourbon_document() -> bytes:
    """The filing: a Registry-shaped text page, then the four pictures.

    The text page states the brand and the class or type, as a Registry
    printout does, and not the alcohol content or the net contents, which is
    where the panels come in (A-17). Page 2 is the front, 3 the back, 4 the
    side band and 5 the signature.
    """
    spec = ApplicationSpec(class_type="Kentucky Straight Bourbon Whiskey")
    return as_pdf_bytes(
        registry_printout_lines(spec),
        images=[
            render_panel_png_bytes(FRONT),
            render_panel_png_bytes(BACK),
            render_panel_png_bytes(SIDE),
            signature_strip(*SIGNATURE),
        ],
    )


def outcomes(body: dict) -> dict[str, str]:
    return {entry["name"]: entry["outcome"] for entry in body["fields"]}


@pytest.fixture(scope="module")
def parsed():
    """The fixture through the parser, once for the module: it costs three reads."""
    return parse_application_document(bourbon_document(), "application/pdf")


@pytest.fixture(scope="module")
def body():
    """The fixture through the route, once for the module."""
    response = client.post(
        "/api/verify", files=[("files", ("bourbon.pdf", bourbon_document(), "application/pdf"))]
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestTheFloorAgainstTheMeasuredFilings:
    """Arithmetic over the measured dimensions. No picture is decoded."""

    def test_the_signature_is_still_excluded(self):
        assert _rejection(*SIGNATURE) == "area"

    def test_four_of_the_bourbon_panels_are_admitted(self):
        verdicts = {size: _rejection(*size) for size in BOURBON_PICTURES}
        assert verdicts == {
            (1103, 340): None,
            (772, 194): "area",
            (1050, 309): None,
            (187, 1697): None,
            (1350, 300): None,
        }

    def test_the_registry_printout_is_no_longer_refused_wholesale(self):
        """Two of its seven pictures clear the floor; at v1.2.0 none did."""
        admitted = [size for size in REGISTRY_PICTURES if _rejection(*size) is None]
        assert admitted == [(1442, 433), (754, 379)]

    def test_the_margin_on_each_side_of_the_floor(self):
        """The two numbers the setting's comment quotes, held to the setting."""
        signature = SIGNATURE[0] * SIGNATURE[1]
        smallest_panel = min(w * h for w, h in BOURBON_PICTURES if _rejection(w, h) is None)
        assert signature == 133_965
        assert smallest_panel == 317_339
        assert signature < settings.min_artwork_pixels <= smallest_panel

    def test_no_shape_rule_could_have_admitted_the_panels_and_excluded_the_signature(self):
        """Why the rules are gone rather than loosened."""
        ratio = lambda w, h: max(w, h) / min(w, h)  # noqa: E731
        panel_ratios = [ratio(w, h) for w, h in BOURBON_PICTURES if _rejection(w, h) is None]
        panel_short_edges = [min(w, h) for w, h in BOURBON_PICTURES if _rejection(w, h) is None]
        # A ceiling admitting every panel admits the signature.
        assert max(panel_ratios) > ratio(*SIGNATURE)
        # An edge floor admitting every panel admits the signature.
        assert min(panel_short_edges) < min(*SIGNATURE)


@requires_tesseract
@requires_fonts
class TestTheBourbonFilingIsRead:
    """The parser, on the fixture. Every panel read, the signature set aside."""

    def test_every_panel_clears_the_floor_and_is_read(self, parsed):
        assert parsed.artwork_images_found == 3
        assert parsed.artwork_images_read == 3
        assert [
            (image.page, image.width, image.height, image.status)
            for image in parsed.artwork_images_accepted
        ] == [
            (2, 1350, 300, "read"),
            (3, 1050, 309, "read"),
            (4, 187, 1697, "read"),
        ]

    def test_the_signature_is_the_only_rejection_and_the_reason_is_area(self, parsed):
        assert [
            (image.page, image.width, image.height, image.reason)
            for image in parsed.artwork_images_rejected
        ] == [(5, 687, 195, "area")]

    def test_the_back_panel_supplies_what_the_text_layer_lacks(self, parsed):
        assert parsed.value_sources["brand_name"] == "embedded_text"
        assert parsed.value_sources["class_type"] == "embedded_text"
        assert parsed.value_sources["alcohol_content"] == "embedded_artwork"
        assert parsed.value_sources["net_contents"] == "embedded_artwork"
        assert "45" in parsed.values["alcohol_content"]
        assert "750" in parsed.values["net_contents"]
        # And the response can say which picture each came off.
        assert parsed.artwork_value_panels["alcohol_content"].page == 3
        assert parsed.artwork_value_panels["net_contents"].page == 3

    def test_every_panel_that_read_is_offered_as_the_label_side(self, parsed):
        """Pooled, largest first among the panels that yielded a value.

        The front carries the brand and the class, the back the alcohol
        content and the net contents, so both yielded values and the larger
        front comes first; the side band yielded none and comes last.
        """
        assert [panel.artwork.page for panel in parsed.label_panels] == [2, 3, 4]
        assert parsed.label_artwork is not None
        assert parsed.label_artwork.page == 2

    def test_the_bound_on_reads_is_reported_rather_than_silent(self, monkeypatch):
        """Past ``max_artwork_images`` a panel is listed as accepted and not read."""
        monkeypatch.setattr(settings, "max_artwork_images", 2)

        parsed = parse_application_document(bourbon_document(), "application/pdf")

        assert parsed.artwork_images_found == 3
        assert parsed.artwork_images_read == 2
        assert [(image.page, image.status) for image in parsed.artwork_images_accepted] == [
            (2, "read"),
            (3, "read"),
            (4, "not_read"),
        ]


@requires_tesseract
@requires_fonts
class TestTheCheckPoolsThePanels:
    """The API, on the fixture alone: five of five, each from the panel it is on."""

    def test_all_five_checks_pass(self, body):
        assert outcomes(body) == {
            "brand_name": "match",
            "class_type": "match",
            "alcohol_content": "present",
            "net_contents": "present",
            "government_warning": "match",
        }

    def test_each_value_names_the_panel_it_was_found_on(self, body):
        """The brand is on the front and the warning on the back, and the
        response says so, the way it says which photograph (ADR 0007)."""
        panels = {photo["index"]: photo["artwork_panel"] for photo in body["photos"]}
        found_on = {entry["name"]: panels[entry["source_photo"]] for entry in body["fields"]}
        assert found_on["brand_name"] == {"page": 2, "width": 1350, "height": 300}
        assert found_on["class_type"] == {"page": 2, "width": 1350, "height": 300}
        assert found_on["alcohol_content"] == {"page": 3, "width": 1050, "height": 309}
        assert found_on["net_contents"] == {"page": 3, "width": 1050, "height": 309}
        assert found_on["government_warning"] == {"page": 3, "width": 1050, "height": 309}

    def test_the_label_side_is_every_panel(self, body):
        assert body["label_source"] == "application_artwork"
        assert [photo["origin"] for photo in body["photos"]] == ["application_artwork"] * 3
        assert all(photo["text_found"] for photo in body["photos"])

    def test_the_response_carries_the_table(self, body):
        """What was read and what was set aside, with sizes, without instrumenting."""
        document = body["application_document"]
        assert [
            (image["width"], image["height"], image["status"])
            for image in document["artwork_images_accepted"]
        ] == [
            (1350, 300, "read"),
            (1050, 309, "read"),
            (187, 1697, "read"),
        ]
        assert document["artwork_images_rejected"] == [
            {"page": 5, "width": 687, "height": 195, "reason": "area"}
        ]
        for image in document["artwork_images_accepted"]:
            assert image["ocr_confidence"] is not None
        parsed = {entry["name"]: entry for entry in document["fields"]}
        assert parsed["alcohol_content"]["artwork_panel"] == {
            "page": 3,
            "width": 1050,
            "height": 309,
        }
        assert parsed["brand_name"]["artwork_panel"] is None

    def test_the_cost_is_one_pass_per_panel_and_no_second_read(self, body):
        """Three panels, three passes, none of them repeated for the label side."""
        timings = body["timings"]
        assert timings["ocr_passes"] == 3
        assert timings["label_ocr_ms"] == 0.0
        assert timings["tesseract_reads"] >= 3

    def test_the_self_consistency_note_still_stands(self, body):
        assert body["self_consistency_note"]


@requires_tesseract
@requires_fonts
class TestTheBulkPathReadsThePanelsToo:
    """A batch row is the same check (ADR 0020), so the same five pass there."""

    def test_a_filed_bourbon_alone_is_a_complete_row(self):
        response = client.post(
            "/api/verify-batch",
            files=[("files", ("bourbon.pdf", bourbon_document(), "application/pdf"))],
        )
        assert response.status_code == 200, response.text
        lines = [line for line in response.text.splitlines() if line.strip()]
        import json

        row = json.loads(lines[-1])
        assert row["status"] == "ok", row
        assert row["result"]["label_source"] == "application_artwork"
        assert outcomes(row["result"]) == {
            "brand_name": "match",
            "class_type": "match",
            "alcohol_content": "present",
            "net_contents": "present",
            "government_warning": "match",
        }


@requires_tesseract
@requires_fonts
class TestBeforeTheChange:
    """What v1.4.0 did to this document, held as a guard against regressing.

    The three shape verdicts are reproduced with the old rules' arithmetic, so
    that anyone tempted to bring a shape rule back sees this fail first.
    """

    def test_the_old_rules_would_reject_every_panel(self):
        old_edge, old_ratio = 400, 3.0
        for width, height in BOURBON_PICTURES:
            assert min(width, height) < old_edge
            assert max(width, height) > old_ratio * min(width, height)

    def test_a_paper_form_with_only_the_panels_is_not_refused(self):
        """The v1.4.0 outcome was ``no_label_to_check``. It is not any more."""
        pdf = as_pdf_bytes(
            paper_form_lines(ApplicationSpec()),
            images=[render_panel_png_bytes(FRONT), render_panel_png_bytes(BACK)],
        )
        response = client.post(
            "/api/verify", files=[("files", ("panels.pdf", pdf, "application/pdf"))]
        )
        assert response.status_code == 200, response.text
        assert response.json()["label_source"] == "application_artwork"
