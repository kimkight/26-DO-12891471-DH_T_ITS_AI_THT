"""More than one photograph of one label, through POST /api/verify (ADR 0007).

Requirements: FR-1 (a field found on any photograph is found), FR-2, FR-3,
FR-9 (all photographs unreadable, and more photographs than the cap, each
return a clear message and no field outcomes), NFR-7. Story: US-22.

A label wraps a round bottle, so no single photograph shows all of it flat. The
cases here are the ones that decision has to get right: fields split across two
photographs, a disagreement between two photographs, one bad photograph among
good ones, the cap, and a single photograph behaving exactly as it always did.
"""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from samples.labelmaker import LabelSpec, render_png_bytes
from samples.specs import SAMPLE_LABEL
from samples.warning_text import WARNING_STATEMENT

from app.config import settings
from app.main import app
from tests.conftest import requires_fonts, requires_tesseract

client = TestClient(app)

pytestmark = [requires_tesseract, requires_fonts]


def verify(photos: list[bytes], application: dict[str, str] | None = None):
    """Submit one label as one or more `image` parts, as the API accepts them."""
    return client.post(
        "/api/verify",
        files=[("image", (f"photo-{n}.png", png, "image/png")) for n, png in enumerate(photos, 1)],
        data=application if application is not None else SAMPLE_LABEL.application,
    )


def label(**overrides) -> bytes:
    return render_png_bytes(LabelSpec(**{**SAMPLE_LABEL.__dict__, **overrides}))


def blank_png(size=(600, 600)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def outcomes(body: dict) -> dict[str, str]:
    return {field["name"]: field["outcome"] for field in body["fields"]}


def sources(body: dict) -> dict[str, int | None]:
    return {field["name"]: field["source_photo"] for field in body["fields"]}


class TestOnePhotographIsUnchanged:
    """The contract that existed before ADR 0007 has to still hold exactly."""

    def test_a_single_photograph_returns_the_same_five_fields(self, sample_label_png):
        body = verify([sample_label_png]).json()
        assert [field["name"] for field in body["fields"]] == [
            "brand_name",
            "class_type",
            "alcohol_content",
            "net_contents",
            "government_warning",
        ]
        assert outcomes(body)["brand_name"] == "match"

    def test_a_single_photograph_reports_exactly_one_photo(self, sample_label_png):
        body = verify([sample_label_png]).json()
        assert len(body["photos"]) == 1
        assert body["photos"][0]["index"] == 1
        assert body["photos"][0]["text_found"] is True

    def test_every_field_found_on_one_photograph_is_attributed_to_it(self, sample_label_png):
        body = verify([sample_label_png]).json()
        for field in body["fields"]:
            if field["found_on_label"]:
                assert field["source_photo"] == 1


class TestFieldsSplitAcrossTwoPhotographs:
    """The case the decision exists for: no one frame shows the whole label.

    The front carries the brand, the class or type and the alcohol content; the
    back carries the net contents and the government warning. Neither photograph
    alone returns a complete result, and together they do.
    """

    @pytest.fixture
    def front(self) -> bytes:
        """Brand, class or type and alcohol content. No net contents, no warning."""
        return label(net_contents=None, warning=None)

    @pytest.fixture
    def back(self) -> bytes:
        """Net contents and the warning, in the small type a back label uses."""
        return label(
            brand_name="",
            class_type="",
            alcohol_content="",
            net_contents="750 mL",
            warning=WARNING_STATEMENT,
        )

    def test_neither_photograph_alone_is_complete(self, front, back):
        """Stated as a test so the next one is known to be proving something."""
        front_only = verify([front]).json()
        net_contents = next(f for f in front_only["fields"] if f["name"] == "net_contents")
        assert net_contents["found_on_label"] is False
        assert outcomes(front_only)["government_warning"] == "mismatch"

        back_only = verify([back]).json()
        assert outcomes(back_only)["brand_name"] != "match"
        abv = next(f for f in back_only["fields"] if f["name"] == "alcohol_content")
        assert abv["found_on_label"] is False

    def test_the_two_together_return_a_complete_result(self, front, back):
        body = verify([front, back]).json()
        found = outcomes(body)
        assert found["brand_name"] == "match"
        assert found["alcohol_content"] == "match"
        assert found["net_contents"] == "match"
        assert found["government_warning"] == "match"

    def test_the_result_says_which_photograph_each_field_came_from(self, front, back):
        came_from = sources(verify([front, back]).json())
        assert came_from["brand_name"] == 1
        assert came_from["alcohol_content"] == 1
        assert came_from["net_contents"] == 2
        assert came_from["government_warning"] == 2

    def test_both_photographs_are_reported(self, front, back):
        body = verify([front, back]).json()
        assert [photo["index"] for photo in body["photos"]] == [1, 2]
        assert all(photo["text_found"] for photo in body["photos"])
        assert all(photo["error"] is None for photo in body["photos"])

    def test_order_does_not_change_the_outcome(self, front, back):
        forward = outcomes(verify([front, back]).json())
        backward = outcomes(verify([back, front]).json())
        assert forward["net_contents"] == backward["net_contents"] == "match"
        assert forward["government_warning"] == backward["government_warning"] == "match"


class TestOneUnreadablePhotographAmongGood:
    """A bad frame does not cost an agent the good ones (FR-8's rule, per label)."""

    def test_the_good_photograph_still_produces_a_result(self, sample_label_png):
        body = verify([blank_png(), sample_label_png]).json()
        assert outcomes(body)["brand_name"] == "match"
        assert sources(body)["brand_name"] == 2

    def test_the_failed_photograph_is_reported_rather_than_hidden(self, sample_label_png):
        body = verify([blank_png(), sample_label_png]).json()
        assert body["photos"][0]["text_found"] is False
        assert body["photos"][0]["error"]["code"] == "no_text_found"
        assert body["photos"][1]["text_found"] is True
        assert body["photos"][1]["error"] is None

    def test_a_corrupt_photograph_among_good_ones_is_the_same(self, sample_label_png):
        response = client.post(
            "/api/verify",
            files=[
                ("image", ("bad.png", b"not an image at all", "image/png")),
                ("image", ("good.png", sample_label_png, "image/png")),
            ],
            data=SAMPLE_LABEL.application,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["photos"][0]["error"]["code"] == "unreadable_image"
        assert outcomes(body)["brand_name"] == "match"


class TestAllPhotographsUnreadable:
    """FR-9: no error path returns a match, and the message names the problem."""

    def test_three_blank_photographs_return_one_clear_failure(self):
        response = verify([blank_png(), blank_png(), blank_png()])
        assert response.status_code == 422
        body = response.json()
        assert "fields" not in body
        assert body["error"]["code"] == "all_photos_unreadable"
        assert "All 3 photographs" in body["error"]["message"]

    def test_a_single_blank_photograph_keeps_the_error_it_always_had(self):
        """One photograph is still one photograph; nothing about it changed."""
        response = verify([blank_png()])
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "no_text_found"

    def test_a_mixed_failure_says_so_rather_than_picking_one(self):
        response = verify([blank_png(), b"not an image at all"])
        assert response.status_code == 422
        message = response.json()["error"]["message"]
        assert "All 2 photographs" in message
        assert "Some could not be decoded" in message


class TestThePhotographCap:
    """NFR-7 and FR-9: refused before any photograph is processed, limit named."""

    def test_four_photographs_are_refused(self, sample_label_png):
        response = verify([sample_label_png] * (settings.max_label_photos + 1))
        assert response.status_code == 413
        error = response.json()["error"]
        assert error["code"] == "too_many_photos"
        assert str(settings.max_label_photos) in error["limit"]

    def test_the_refusal_carries_no_field_outcomes(self, sample_label_png):
        response = verify([sample_label_png] * (settings.max_label_photos + 1))
        assert "fields" not in response.json()
        assert "match" not in response.text

    def test_exactly_the_cap_is_accepted(self, sample_label_png):
        response = verify([sample_label_png] * settings.max_label_photos)
        assert response.status_code == 200
        assert len(response.json()["photos"]) == settings.max_label_photos


class TestDisagreementBetweenPhotographs:
    """ADR 0007's consequence: the better-read photograph wins, and says so."""

    def test_the_clearer_photograph_supplies_a_pattern_located_field(self, sample_label_png):
        """Net contents is found by pattern, so confidence is what decides."""
        faint = label(low_contrast=True)
        body = verify([faint, sample_label_png]).json()
        assert sources(body)["net_contents"] == 2
        assert outcomes(body)["net_contents"] == "match"

    def test_the_brand_name_comes_from_the_photograph_that_shows_it_largest(self):
        """Not from the one that reads most confidently. A back label's small
        print is read perfectly and is not the brand name."""
        front = label(net_contents=None, warning=None)
        back = label(brand_name="", class_type="", alcohol_content="", net_contents="750 mL")
        body = verify([back, front]).json()
        assert sources(body)["brand_name"] == 2
        assert outcomes(body)["brand_name"] == "match"

    def test_a_photograph_that_cuts_the_warning_off_does_not_win_it(self, sample_label_png):
        """The truncated read is confident and wrong, so length decides."""
        truncated = label(
            warning="GOVERNMENT WARNING: (1) According to the Surgeon General, women should"
        )
        body = verify([truncated, sample_label_png]).json()
        assert sources(body)["government_warning"] == 2
        assert outcomes(body)["government_warning"] == "match"

    def test_an_altered_warning_is_still_reported_when_it_is_the_only_one(self):
        """FR-5 is not softened: more photographs does not mean more forgiving."""
        altered = label(
            warning=WARNING_STATEMENT.replace("should not drink", "should avoid drinking")
        )
        body = verify([label(warning=None), altered]).json()
        assert outcomes(body)["government_warning"] == "mismatch"


class TestTheBatchPathIsUnaffected:
    def test_the_batch_route_still_takes_one_image_per_row(self, sample_label_png):
        """ADR 0007 leaves the batch path at one photograph per row this session."""
        response = client.post(
            "/api/verify-batch",
            files=[
                ("images", ("01.png", sample_label_png, "image/png")),
                (
                    "applications",
                    (
                        "applications.csv",
                        b"filename,brand_name,class_type,alcohol_content,net_contents,"
                        b"beverage_type\n01.png,Stone's Throw,Kentucky Straight Bourbon "
                        b"Whiskey,45,750 mL,distilled spirits\n",
                        "text/csv",
                    ),
                ),
            ],
        )
        assert response.status_code == 200
        line = response.text.strip().splitlines()[0]
        assert '"filename": "01.png"' in line or '"filename":"01.png"' in line


class TestWhatThreePhotographsCost:
    """NFR-1, measured and printed rather than asserted (ADR 0007).

    Reading three photographs is three reads. On a session runner that lands
    inside NFR-1's five-second target with about a second to spare, which is too
    thin a margin to gate on: a runner's timings vary enough that a failure here
    would say nothing about the change that caused it. That is the rule
    docs/07_TEST_STRATEGY.md section 7 already applies to the performance tier.
    The single-photograph assertion in test_verify_integration.py does gate,
    because it has four seconds of headroom.
    """

    def test_the_cost_of_one_two_and_three_photographs_is_reported(self, sample_label_png, capsys):
        import time

        measured = []
        for count in range(1, settings.max_label_photos + 1):
            started = time.perf_counter()
            response = verify([sample_label_png] * count)
            measured.append((count, time.perf_counter() - started))
            assert response.status_code == 200

        with capsys.disabled():
            print("\nCost of reading more than one photograph of one label (ADR 0007):")
            for count, elapsed in measured:
                print(
                    f"  {count} photograph{'s' if count > 1 else ' '}: {elapsed:.2f} s end to end. "
                    "Measured on this runner, not on production hardware."
                )
            print("  NFR-1's target is about 5 s. Not gated; see the docstring.")

        # The only thing asserted is that the cost scales rather than explodes:
        # three photographs should not cost more than four single ones, which
        # would mean something other than the reads is growing with the count.
        assert measured[-1][1] < measured[0][1] * (settings.max_label_photos + 1)
