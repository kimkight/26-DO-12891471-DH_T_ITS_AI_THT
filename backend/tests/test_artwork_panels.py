"""A filing whose labels are embedded as separate panels (#121, OQ-24, ADR 0010).

The author put a second real filed COLA, a bourbon, through the deployed
v1.4.0 build on 2026-09-03. One of five checks passed. The reader never saw the
label: of six embedded pictures, five were rejected before any was read, every
one of them on ``short_edge``, and the aspect-ratio rule would have rejected
four of them next. v1.5.0 removed the two shape rules and read every panel up
to a fixed count of four. Measured on that build, the same document read four
of its five panels, matched the brand and the class or type, and still
reported the alcohol content, the net contents and the government warning as
not found, at 7,325 ms and 16 Tesseract reads against 2,600 ms and 4 before:

======  ==========  =========  ======  ==============  ==============
page    size        area       ratio   at v1.4.0       at v1.5.0 as merged
======  ==========  =========  ======  ==============  ==============
2       1950 x 862  1,680,900  2.26    read, 45.3      read, 45.3
4       1350 x 300    405,000  4.50    short_edge      read, 89.9
2       1103 x 340    375,020  3.24    short_edge      read, 29.0
3       1050 x 309    324,450  3.40    short_edge      read, 86.8
3        187 x 1697   317,339  9.07    short_edge      **not read**
2        772 x 194    149,768  3.98    short_edge      area
======  ==========  =========  ======  ==============  ==============

The 187 by 1697 side strip is the smallest of the five and the fourth-place
count dropped it, and a tall narrow strip is exactly where a spirits label
carries its government warning, alcohol statement and net contents. The two
panels the shape rules had thrown away read at 86.8 and 89.9, better than the
45.3 of the wide sheet the rules kept, so neither size nor shape says which
panel carries a value. Reading stops now when the panels read so far carry all
five values, and the count is a ceiling on the worst case rather than the
thing that decides whether a value is found (ADR 0010 as amended a second
time).

This fixture is that filing's shape with synthetic text: a 1950 by 862 sheet
carrying the class or type and prose, a 1350 by 300 front panel carrying the
brand and the class or type, a 1103 by 340 wrap-around and a 1050 by 309 back
panel carrying prose, a 187 by 1697 side strip carrying the alcohol content,
the net contents and the government warning, and a 687 by 195 signature.
Neither of the author's documents is in the repository; only the dimensions
are. With the count at four and no stopping rule this document returned two of
five; now all five checks pass, each attributed to the panel it is on, and the
signature is still excluded. It is the regression test OQ-24 asked for.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from samples.formmaker import (  # noqa: E402
    ApplicationSpec,
    as_pdf_bytes,
    paper_form_lines,
    registry_printout_lines,
)
from samples.labelmaker import PanelSpec, render_panel_png_bytes, render_png_bytes  # noqa: E402
from samples.specs import SAMPLE_LABEL  # noqa: E402

from app.application_form import (  # noqa: E402
    _rejection,
    _satisfied,
    parse_application_document,
)
from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.parse import lines_from_text, parse_fields  # noqa: E402
from app.search import label_units  # noqa: E402
from app.warning import WARNING_STATEMENT  # noqa: E402
from tests.conftest import requires_fonts, requires_tesseract  # noqa: E402
from tests.test_embedded_artwork import signature_strip  # noqa: E402

client = TestClient(app)

# The bourbon filing's pictures, as measured on the deployed v1.4.0 and v1.5.0
# builds. The first is the one v1.4.0 read; the count of four at v1.5.0 kept
# the first four and left the strip.
BOURBON_PICTURES = (
    (1950, 862),
    (1103, 340),
    (772, 194),
    (1050, 309),
    (187, 1697),
    (1350, 300),
)
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

# The five panels, in the order the fixture embeds them, which is also their
# rank by area. No word on a prose panel is one the check searches for.
SHEET = PanelSpec(
    1950,
    862,
    (
        "Kentucky Straight Bourbon Whiskey",
        "Aged four years in new charred oak barrels",
        "Distilled and bottled by Example Distilling Company, Anytown",
    ),
)
FRONT = PanelSpec(1350, 300, ("STONE'S THROW", "Kentucky Straight Bourbon Whiskey"))
WRAP = PanelSpec(1103, 340, ("Small batch", "Hand selected barrels from the Example rickhouse"))
BACK = PanelSpec(
    1050, 309, ("Since 1889", "Made in Anytown from local corn, rye and malted barley")
)
SIDE = PanelSpec(
    187, 1697, ("45% Alc./Vol. (90 Proof)", "750 ML", WARNING_STATEMENT), vertical=True
)
PANELS = (SHEET, FRONT, WRAP, BACK, SIDE)
# Where the fixture puts each of the five values: the page of the panel.
SHEET_PAGE, FRONT_PAGE, WRAP_PAGE, BACK_PAGE, SIDE_PAGE, SIGNATURE_PAGE = range(2, 8)


def bourbon_document() -> bytes:
    """The filing: a Registry-shaped text page, then the six pictures.

    The text page states the brand and the class or type, as a Registry
    printout does, and not the alcohol content or the net contents, which is
    where the panels come in (A-17). Page 2 is the sheet, 3 the front, 4 the
    wrap-around, 5 the back, 6 the side strip and 7 the signature.
    """
    spec = ApplicationSpec(class_type="Kentucky Straight Bourbon Whiskey")
    return as_pdf_bytes(
        registry_printout_lines(spec),
        images=[render_panel_png_bytes(panel) for panel in PANELS] + [signature_strip(*SIGNATURE)],
    )


def outcomes(body: dict) -> dict[str, str]:
    return {entry["name"]: entry["outcome"] for entry in body["fields"]}


def found_on(body: dict) -> dict[str, int | None]:
    """The page each check's value was found on, or None where it was not."""
    pages = {photo["index"]: photo["artwork_panel"]["page"] for photo in body["photos"]}
    return {
        entry["name"]: None if entry["source_photo"] is None else pages[entry["source_photo"]]
        for entry in body["fields"]
    }


@pytest.fixture(scope="module")
def parsed():
    """The fixture through the parser, once for the module: it costs five reads."""
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

    def test_five_of_the_bourbon_pictures_are_admitted(self):
        verdicts = {size: _rejection(*size) for size in BOURBON_PICTURES}
        assert verdicts == {
            (1950, 862): None,
            (1103, 340): None,
            (772, 194): "area",
            (1050, 309): None,
            (187, 1697): None,
            (1350, 300): None,
        }

    def test_the_ceiling_is_above_the_count_a_real_filing_carries(self):
        """Five above the floor on the bourbon; the ceiling was four.

        A ceiling inside the count a measured filing embeds is a ceiling that
        decides whether a value is found, which is what it did on 2026-09-03.
        """
        admitted = sum(1 for size in BOURBON_PICTURES if _rejection(*size) is None)
        assert admitted == 5
        assert settings.max_artwork_images > admitted

    def test_the_strip_ranks_last_by_area(self):
        """The panel carrying three of the five values is the one a count drops."""
        admitted = sorted(
            (size for size in BOURBON_PICTURES if _rejection(*size) is None),
            key=lambda size: -(size[0] * size[1]),
        )
        assert admitted[-1] == (187, 1697)
        assert admitted[:4] == [(1950, 862), (1350, 300), (1103, 340), (1050, 309)]

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


class TestTheStoppingRule:
    """``_satisfied`` on readings built from text. No picture is decoded.

    The rule asks the check's question, not the panel's: whether the declared
    brand and class or type appear on the panels read so far by the same
    search the check makes, and whether the other three were located.
    """

    FULL = (
        "STONE'S THROW\nKentucky Straight Bourbon Whiskey\n"
        f"45% Alc./Vol. (90 Proof)\n750 mL\n{WARNING_STATEMENT}"
    )
    DECLARED = {"brand_name": "STONE'S THROW", "class_type": "Kentucky Straight Bourbon Whiskey"}

    @staticmethod
    def satisfied(text: str, declared: dict[str, str]) -> bool:
        lines = lines_from_text(text)
        return _satisfied([parse_fields(lines)], label_units(lines), declared)

    def test_all_five_on_one_panel_stops(self):
        assert self.satisfied(self.FULL, self.DECLARED) is True

    def test_a_declared_brand_the_panel_does_not_carry_does_not_stop(self):
        """The panel has a largest line, and it is not the brand.

        A back label prints the distiller's name in large type above the
        alcohol content, the net contents and the warning. A rule that took
        the largest text as the brand would stop here and never read the
        front; the check would then search for the declared brand and not
        find it. So the rule searches for what is declared.
        """
        text = self.FULL.replace("STONE'S THROW", "Example Distilling Company")
        assert self.satisfied(text, self.DECLARED) is False

    def test_a_near_miss_on_the_brand_does_not_stop(self):
        """A hit in the review band is not enough: a later panel may print it cleanly."""
        text = self.FULL.replace("STONE'S THROW", "STONE'S THROVV")
        assert self.satisfied(text, self.DECLARED) is False

    def test_with_nothing_declared_the_panels_own_reading_stands_in(self):
        """A scan with no text layer declares nothing; the check falls back the same way."""
        assert self.satisfied(self.FULL, {}) is True

    def test_a_declared_class_with_a_registry_code_is_searched_without_it(self):
        declared = dict(self.DECLARED, class_type="Kentucky Straight Bourbon Whiskey 101")
        assert self.satisfied(self.FULL, declared) is True

    @pytest.mark.parametrize(
        "missing",
        [
            pytest.param(WARNING_STATEMENT, id="no warning"),
            pytest.param("750 mL\n", id="no net contents"),
            pytest.param("45% Alc./Vol. (90 Proof)\n", id="no alcohol content"),
        ],
    )
    def test_any_one_of_the_other_three_missing_does_not_stop(self, missing):
        assert self.satisfied(self.FULL.replace(missing, ""), self.DECLARED) is False

    def test_the_values_may_be_spread_over_several_readings(self):
        """The front carries two, the strip three; together they satisfy it."""
        front = lines_from_text("STONE'S THROW\nKentucky Straight Bourbon Whiskey")
        strip = lines_from_text(f"45% Alc./Vol. (90 Proof)\n750 mL\n{WARNING_STATEMENT}")
        readings = [parse_fields(front), parse_fields(strip)]
        units = label_units(front) + label_units(strip)
        assert _satisfied(readings[:1], label_units(front), self.DECLARED) is False
        assert _satisfied(readings, units, self.DECLARED) is True


@requires_tesseract
@requires_fonts
class TestTheBourbonFilingIsRead:
    """The parser, on the fixture. Every panel read, the signature set aside."""

    def test_every_panel_clears_the_floor_and_is_read(self, parsed):
        assert parsed.artwork_images_found == 5
        assert parsed.artwork_images_read == 5
        assert [
            (image.page, image.width, image.height, image.status)
            for image in parsed.artwork_images_accepted
        ] == [
            (SHEET_PAGE, 1950, 862, "read"),
            (FRONT_PAGE, 1350, 300, "read"),
            (WRAP_PAGE, 1103, 340, "read"),
            (BACK_PAGE, 1050, 309, "read"),
            (SIDE_PAGE, 187, 1697, "read"),
        ]

    def test_the_signature_is_the_only_rejection_and_the_reason_is_area(self, parsed):
        assert [
            (image.page, image.width, image.height, image.reason)
            for image in parsed.artwork_images_rejected
        ] == [(SIGNATURE_PAGE, 687, 195, "area")]

    def test_the_strip_supplies_what_the_text_layer_lacks(self, parsed):
        assert parsed.value_sources["brand_name"] == "embedded_text"
        assert parsed.value_sources["class_type"] == "embedded_text"
        assert parsed.value_sources["alcohol_content"] == "embedded_artwork"
        assert parsed.value_sources["net_contents"] == "embedded_artwork"
        assert "45" in parsed.values["alcohol_content"]
        assert "750" in parsed.values["net_contents"]
        # And the response can say which picture each came off: the strip.
        assert parsed.artwork_value_panels["alcohol_content"].page == SIDE_PAGE
        assert parsed.artwork_value_panels["net_contents"].page == SIDE_PAGE

    def test_every_panel_that_read_is_offered_as_the_label_side(self, parsed):
        """Pooled, in rank order: every panel here yielded some value."""
        assert [panel.artwork.page for panel in parsed.label_panels] == [
            SHEET_PAGE,
            FRONT_PAGE,
            WRAP_PAGE,
            BACK_PAGE,
            SIDE_PAGE,
        ]
        assert parsed.label_artwork is not None
        assert parsed.label_artwork.page == SHEET_PAGE

    def test_the_ceiling_is_reported_rather_than_silent(self, monkeypatch):
        """Past ``max_artwork_images`` a panel is listed as accepted and not read.

        This is what v1.5.0 as merged did to the bourbon with the ceiling at
        four: the strip, ranked fifth, was never looked at, and the three
        values on it came back absent. Held here so the defect stays
        reproducible, and distinguishable from ``not_needed``.
        """
        monkeypatch.setattr(settings, "max_artwork_images", 4)

        parsed = parse_application_document(bourbon_document(), "application/pdf")

        assert parsed.artwork_images_found == 5
        assert parsed.artwork_images_read == 4
        assert [(image.page, image.status) for image in parsed.artwork_images_accepted] == [
            (SHEET_PAGE, "read"),
            (FRONT_PAGE, "read"),
            (WRAP_PAGE, "read"),
            (BACK_PAGE, "read"),
            (SIDE_PAGE, "not_read"),
        ]
        assert parsed.values["alcohol_content"] is None
        assert parsed.values["net_contents"] is None


@requires_tesseract
@requires_fonts
class TestReadingStopsWhenTheValuesAreInHand:
    """The stopping rule on real reads (ADR 0010 as amended a second time)."""

    def test_a_sheet_that_carries_everything_is_the_only_panel_read(self):
        """One flat sheet ahead of two prose panels: one read, two not needed."""
        pdf = as_pdf_bytes(
            paper_form_lines(ApplicationSpec()),
            images=[
                render_png_bytes(SAMPLE_LABEL),
                render_panel_png_bytes(WRAP),
                render_panel_png_bytes(BACK),
            ],
        )

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.artwork_images_found == 3
        assert parsed.artwork_images_read == 1
        assert [
            (image.page, image.status, image.ocr_confidence is not None)
            for image in parsed.artwork_images_accepted
        ] == [
            (2, "read", True),
            (3, "not_needed", False),
            (4, "not_needed", False),
        ]
        assert [panel.artwork.page for panel in parsed.label_panels] == [2]

    def test_the_stop_asks_the_checks_question_and_not_the_panels(self):
        """A back panel with the distiller's name in large type is read first.

        It carries the alcohol content, the net contents and the warning, and
        its largest text is not the brand. The reading must go on to the
        smaller front, which is where the declared brand is; only then is the
        third panel not needed.
        """
        back = PanelSpec(
            1950,
            862,
            ("Example Distilling Company", "45% Alc./Vol. (90 Proof)", "750 ML", WARNING_STATEMENT),
        )
        pdf = as_pdf_bytes(
            registry_printout_lines(ApplicationSpec()),
            images=[
                render_panel_png_bytes(back),
                render_panel_png_bytes(FRONT),
                render_panel_png_bytes(WRAP),
            ],
        )

        parsed = parse_application_document(pdf, "application/pdf")

        assert [(image.page, image.status) for image in parsed.artwork_images_accepted] == [
            (2, "read"),
            (3, "read"),
            (4, "not_needed"),
        ]
        assert parsed.artwork_value_panels["alcohol_content"].page == 2

    def test_a_document_missing_a_value_reads_every_panel(self):
        """The full sweep, which is the one case where it is doing real work."""
        pdf = as_pdf_bytes(
            registry_printout_lines(ApplicationSpec()),
            images=[render_panel_png_bytes(panel) for panel in (SHEET, FRONT, WRAP, BACK)],
        )

        parsed = parse_application_document(pdf, "application/pdf")

        assert parsed.artwork_images_read == 4
        assert all(image.status == "read" for image in parsed.artwork_images_accepted)
        assert parsed.values["alcohol_content"] is None

    def test_the_route_reports_one_pass_and_the_rest_as_not_needed(self):
        pdf = as_pdf_bytes(
            paper_form_lines(ApplicationSpec()),
            images=[render_png_bytes(SAMPLE_LABEL), render_panel_png_bytes(WRAP)],
        )
        response = client.post(
            "/api/verify", files=[("files", ("sheet.pdf", pdf, "application/pdf"))]
        )
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["timings"]["ocr_passes"] == 1
        assert [
            image["status"] for image in body["application_document"]["artwork_images_accepted"]
        ] == ["read", "not_needed"]
        assert len(body["photos"]) == 1


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
        """The brand is on the front, the other three on the strip, and the
        response says so, the way it says which photograph (ADR 0007). The
        class or type is found on the first panel to print it, the sheet."""
        assert found_on(body) == {
            "brand_name": FRONT_PAGE,
            "class_type": SHEET_PAGE,
            "alcohol_content": SIDE_PAGE,
            "net_contents": SIDE_PAGE,
            "government_warning": SIDE_PAGE,
        }
        panels = {photo["index"]: photo["artwork_panel"] for photo in body["photos"]}
        strip = next(entry for entry in body["fields"] if entry["name"] == "government_warning")
        assert panels[strip["source_photo"]] == {"page": SIDE_PAGE, "width": 187, "height": 1697}

    def test_the_label_side_is_every_panel(self, body):
        assert body["label_source"] == "application_artwork"
        assert [photo["origin"] for photo in body["photos"]] == ["application_artwork"] * 5
        assert all(photo["text_found"] for photo in body["photos"])

    def test_the_response_carries_the_table(self, body):
        """What was read and what was set aside, with sizes, without instrumenting."""
        document = body["application_document"]
        assert [
            (image["width"], image["height"], image["status"])
            for image in document["artwork_images_accepted"]
        ] == [
            (1950, 862, "read"),
            (1350, 300, "read"),
            (1103, 340, "read"),
            (1050, 309, "read"),
            (187, 1697, "read"),
        ]
        assert document["artwork_images_rejected"] == [
            {"page": SIGNATURE_PAGE, "width": 687, "height": 195, "reason": "area"}
        ]
        for image in document["artwork_images_accepted"]:
            assert image["ocr_confidence"] is not None
        parsed = {entry["name"]: entry for entry in document["fields"]}
        assert parsed["alcohol_content"]["artwork_panel"] == {
            "page": SIDE_PAGE,
            "width": 187,
            "height": 1697,
        }
        assert parsed["brand_name"]["artwork_panel"] is None

    def test_the_cost_is_one_pass_per_panel_and_no_second_read(self, body):
        """Five panels, five passes, none of them repeated for the label side.

        Five, not fewer: the last value is on the last panel, so the stopping
        rule recovers nothing on this shape and the sweep is the cost of
        finding what the filing spread out. It is the one-sheet filing, and
        the two-panel front-and-back, that the rule makes cheaper.
        """
        timings = body["timings"]
        assert timings["ocr_passes"] == 5
        assert timings["label_ocr_ms"] == 0.0
        assert timings["tesseract_reads"] >= 5

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
    """What the two earlier builds did to this document, held as guards.

    The shape verdicts are reproduced with the v1.4.0 rules' arithmetic, so
    that anyone tempted to bring a shape rule back sees this fail first; and
    the v1.5.0 outcome is reproduced with its count of four, so that anyone
    tempted to lower the ceiling into the range a real filing occupies sees
    what it costs.
    """

    def test_the_old_rules_would_reject_every_panel_but_the_sheet(self):
        old_edge, old_ratio = 400, 3.0
        for width, height in BOURBON_PICTURES:
            if (width, height) == (1950, 862):
                continue
            assert min(width, height) < old_edge
            assert max(width, height) > old_ratio * min(width, height)

    def test_a_count_of_four_returns_two_of_five(self, monkeypatch):
        """v1.5.0 as merged: brand and class match, three values not found."""
        monkeypatch.setattr(settings, "max_artwork_images", 4)
        response = client.post(
            "/api/verify",
            files=[("files", ("bourbon.pdf", bourbon_document(), "application/pdf"))],
        )
        assert response.status_code == 200, response.text
        body = response.json()

        assert outcomes(body) == {
            "brand_name": "match",
            "class_type": "match",
            "alcohol_content": "mismatch",
            "net_contents": "mismatch",
            "government_warning": "mismatch",
        }
        assert body["timings"]["ocr_passes"] == 4
        assert [
            image["status"] for image in body["application_document"]["artwork_images_accepted"]
        ][-1] == "not_read"

    def test_a_paper_form_with_only_the_panels_is_not_refused(self):
        """The v1.4.0 outcome was ``no_label_to_check``. It is not any more."""
        pdf = as_pdf_bytes(
            paper_form_lines(ApplicationSpec()),
            images=[render_panel_png_bytes(FRONT), render_panel_png_bytes(SIDE)],
        )
        response = client.post(
            "/api/verify", files=[("files", ("panels.pdf", pdf, "application/pdf"))]
        )
        assert response.status_code == 200, response.text
        assert response.json()["label_source"] == "application_artwork"


def _png_size(content: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(content)).size


@requires_fonts
def test_the_fixture_is_the_shape_it_claims():
    """The rendered panels are the measured sizes, so the floor test is real."""
    for panel in PANELS:
        assert _png_size(render_panel_png_bytes(panel)) == (panel.width, panel.height)
