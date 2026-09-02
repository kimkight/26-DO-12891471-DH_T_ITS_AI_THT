"""Item 5 of TTB F 5100.31: read the ticked box out of the rendered page.

Governing requirements: FR-11 (the label application as an input), FR-1 (report
not found rather than a guess), NFR-3 (nothing here reaches the network),
NFR-6 (nothing about the document is logged or kept). Assumption A-17, amended.
Decision reference: [ADR 0016](../../docs/adr/0016-product-type-from-the-page.md).

**Item 5 is a field, it is required, and the tool has been leaving it blank.**
"TYPE OF PRODUCT (Required)" is three check boxes, WINE, DISTILLED SPIRITS and
MALT BEVERAGES. A text layer prints the caption of an unticked box exactly as it
prints the caption of a ticked one, so a document naming all three has said
nothing about which was chosen, and ``app.application_form._sole_product_type``
correctly refuses to guess from it. An AcroForm field answers it on an
applicant's unflattened copy of the downloadable form, and that path already
works. What was left was every other filing: a flattened, printed or scanned
copy, where the tick is in the pixels and nowhere else.

**The pixels are already there.** The tool renders the document's pages
(``app.application_form._render_page``), and on the author's own filing, rendered
at scale 2.0, the ticked box is plainly darker than the two empty ones:

    ====================  ===============
    item 5 option          mean luminance
    ====================  ===============
    WINE                            239.9
    **DISTILLED SPIRITS**       **217.5**
    MALT BEVERAGE                   241.8
    ====================  ===============

A 22 point separation on deliberately loose coordinates, taken by hand. The two
empty boxes differ from each other by 1.9, which is what two boxes that are the
same look like. Item 3, SOURCE OF PRODUCT, shows the same pattern with
"Imported" ticked.

**The window this module takes measures less.** Run through the pipeline at
v1.2.0, the same filing separates by 12.1 points with ``_checkbox_of``'s
window, against a ``PRODUCT_TYPE_MARGIN`` of 12.0; a single-page Registry
printout measured 32.3 on the same day. The margin therefore sits at the edge
of the signal on the document it was set from, and a change of render scale or
edition could flip a correct reading to "not determined". Tracked as #123; the
number is not moved until the measurement has been taken across both documents
at three scales.

**This is the same lesson as the embedded label artwork, in a second place: the
form is a picture as well as a text layer, and the tool has to look at both.**
That is the through-line of the last three defect sessions, and it is written
into ADR 0016 rather than left here.

**Nothing here is compared against the label.** The beverage type selects which
numeric rule runs, A-12's proof cross-check for spirits or A-13's ranges for
wine, and the result panel already names the rule that ran. It is surfaced for
confirmation and stays editable like every other parsed value.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
import pytesseract
from PIL import Image
from pytesseract import Output

from app import timing

# The three options, in the words this application uses everywhere else, mapped
# to the caption words the form prints. The plural is optional on the last one
# because the form prints MALT BEVERAGES and this application says malt
# beverage; matching the stem is what keeps the two from having to agree.
OPTIONS: dict[str, tuple[str, ...]] = {
    "wine": ("wine",),
    "distilled spirits": ("distilled", "spirits"),
    "malt beverage": ("malt", "beverage"),
}

# The same three, as strings to search a PDF text layer for. Singular on the last
# one so that "MALT BEVERAGE" is found inside the form's own "MALT BEVERAGES";
# the search is a substring search, and the check box sits to the left of the
# first word either way.
#
# A spurious match is the safe direction to be wrong in. All three captions have
# to be found before anything is sampled, and a caption matched somewhere it does
# not belong puts a sample window over blank paper, which reads near white and
# therefore cannot become the darkest of the three.
CAPTION_TEXT: dict[str, str] = {
    "wine": "WINE",
    "distilled spirits": "DISTILLED SPIRITS",
    "malt beverage": "MALT BEVERAGE",
}

# The check box sits immediately to the left of its caption, and everything
# below is expressed in **caption text heights** rather than pixels.
#
# **Not one pixel coordinate anywhere**, which is the constraint the author set
# and the reason it is set: the form has editions, this tool renders at a scale
# derived from the page size and a setting, and a coordinate measured on one
# render of one edition is a number that happens to be right once. A caption is
# located by its own words and the box is placed relative to that caption, so the
# rule survives a different edition, a different scale, and a scan at a different
# resolution.
#
# The window is a square reaching left from just short of the caption, sized in
# caption text heights: wide enough and tall enough to contain a check box of
# anything from about one to about two caption heights, with slack around it.
#
# **Loose on purpose, and the reason is not laziness.** A tight crop on the box's
# interior gives a bigger number when it lands exactly, and a wrong answer when it
# does not: on a page rendered small enough that a caption is twelve pixels high,
# a one-pixel difference in where OCR put a caption's left edge moved a tight
# window onto one box's printed rule and off another's, and produced a fifteen
# point difference between two boxes that were both empty. A window that
# comfortably contains the whole box contains both rules for every option, so the
# baseline is the same for all three and only a tick moves it. The author's own
# measurement was taken on "deliberately loose coordinates" and separated by 22
# points, which is the same finding from the other direction.
_WINDOW_SIZE_RATIO = 2.4
_WINDOW_GAP_RATIO = 0.25

# How much darker the darkest box has to be than the next darkest before it is
# called ticked, in luminance points on the 0 to 255 scale.
#
# **The number is set from both ends of the author's measurement.** The signal on
# her own filing is 22.4 points, from a loose crop that this module does not take;
# this module's own window measures 12.1 on that filing (#123, see the module
# docstring), which is why the margin is not to be raised without a new measurement.
# The noise is 1.9 points, which is the difference between her two *empty* boxes
# and therefore the size of a difference that means nothing: paper texture, a
# heavier printed rule on one box, a scanner's uneven illumination.
#
# 12.0 sits between them and not in the middle of them. It is about half the
# observed signal, so a tick half as dark as hers is still read; and about six
# times the observed noise, so a difference produced by the paper is not. Erring
# towards the noise floor would be the expensive direction to be wrong in: FR-1's
# rule is that a value the tool cannot identify is reported as not found rather
# than guessed, and a wrongly-read product type would silently select the wrong
# numeric rule.
#
# Where the separation falls short, or where the captions could not be located at
# all, this returns nothing and the agent chooses, exactly as they do today.
PRODUCT_TYPE_MARGIN = 12.0


@dataclass(frozen=True)
class CaptionBox:
    """Where one item 5 caption sits on the rendered page, in its pixels.

    ``option`` is the key from ``OPTIONS``. The four edges are in pixels of the
    render the boxes were located on, and are only meaningful against that same
    render, which is why the two always travel together.
    """

    option: str
    left: float
    top: float
    right: float
    bottom: float

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def centre_y(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass(frozen=True)
class ProductTypeReading:
    """What item 5's three boxes were read to say, and on what evidence.

    ``value`` is None wherever the answer was not clear, which covers a page
    whose captions could not be found, a page where two boxes are equally dark,
    and a page where none of them is filled. All three are reported the same way
    to a caller, and the reason says which happened.
    """

    value: str | None
    luminance: dict[str, float] = field(default_factory=dict)
    separation: float | None = None
    reason: str = ""

    @property
    def sampled(self) -> bool:
        """Whether all three boxes were actually located and measured.

        The difference between this and ``value is None`` is the difference
        between "the boxes say no single one is ticked" and "there were no boxes
        to look at". A caller deciding whether this reading outranks something
        else needs the first and not the second.
        """
        return len(self.luminance) == len(OPTIONS)


NOT_LOCATED = (
    "Item 5's three check box captions were not all found on this page, so there "
    "was nothing to sample. The type of product was not determined."
)


def read_product_type(page_png: bytes, captions: list[CaptionBox]) -> ProductTypeReading:
    """Sample the three item 5 boxes on one rendered page and decide (A-17).

    Returns the darkest option **only where it is clear of the next darkest by
    ``PRODUCT_TYPE_MARGIN``**. Two boxes within the margin of each other, and
    three boxes that are all empty, both come back as not determined, because on
    this evidence they are the same situation: nothing about the page says which
    one was chosen.
    """
    if {caption.option for caption in captions} != set(OPTIONS):
        return ProductTypeReading(value=None, reason=NOT_LOCATED)

    page = _grayscale(page_png)
    luminance = {
        caption.option: _mean_luminance(page, _checkbox_of(caption)) for caption in captions
    }
    readable = {option: value for option, value in luminance.items() if value is not None}
    if len(readable) != len(OPTIONS):
        return ProductTypeReading(
            value=None,
            luminance={option: round(value, 1) for option, value in readable.items()},
            reason=(
                "At least one of item 5's check boxes fell outside the rendered "
                "page, so the three could not be compared. The type of product "
                "was not determined."
            ),
        )

    ordered = sorted(readable.items(), key=lambda entry: entry[1])
    darkest, second = ordered[0], ordered[1]
    separation = second[1] - darkest[1]
    measured = {option: round(value, 1) for option, value in readable.items()}

    if separation < PRODUCT_TYPE_MARGIN:
        return ProductTypeReading(
            value=None,
            luminance=measured,
            separation=round(separation, 1),
            reason=(
                f"Item 5's check boxes were sampled and the darkest, {darkest[0]}, "
                f"is only {separation:.1f} luminance points darker than the next, "
                f"{second[0]}. That is inside the {PRODUCT_TYPE_MARGIN:g} point "
                "margin this tool requires, so either no box is ticked or two are "
                "too close to separate. The type of product was not determined; "
                "choose it yourself."
            ),
        )

    return ProductTypeReading(
        value=darkest[0],
        luminance=measured,
        separation=round(separation, 1),
        reason=(
            f"Item 5's {darkest[0]} box is {separation:.1f} luminance points "
            f"darker than the next darkest, {second[0]}, which clears the "
            f"{PRODUCT_TYPE_MARGIN:g} point margin. Read from the rendered page, "
            "because a ticked box is not in a document's text layer (A-17)."
        ),
    )


def _checkbox_of(caption: CaptionBox) -> tuple[int, int, int, int]:
    """The sample window for one caption's box, as (left, top, right, bottom).

    Placed relative to the caption and sized in caption text heights, so the same
    arithmetic holds at any render scale and at any edition's type size.

    The right edge stops short of the caption rather than growing towards it. The
    slack is spent leftwards and vertically, where there is nothing but paper and
    the box; spending it rightwards would pull the caption's own first letter into
    the sample, and the three captions begin with three different letters, which
    would put a difference between the options that has nothing to do with which
    one is ticked.
    """
    size = caption.height * _WINDOW_SIZE_RATIO
    right = caption.left - caption.height * _WINDOW_GAP_RATIO
    top = caption.centre_y - size / 2
    return (
        int(round(right - size)),
        int(round(top)),
        int(round(right)),
        int(round(top + size)),
    )


def _grayscale(page_png: bytes) -> np.ndarray:
    """The rendered page as a 2-D array of luminance, 0 black to 255 white."""
    with Image.open(io.BytesIO(page_png)) as image:
        return np.asarray(image.convert("L"), dtype=np.float64)


def _mean_luminance(page: np.ndarray, window: tuple[int, int, int, int]) -> float | None:
    """Mean luminance inside one window, or None where it is off the page."""
    left, top, right, bottom = window
    height, width = page.shape
    left, top = max(left, 0), max(top, 0)
    right, bottom = min(right, width), min(bottom, height)
    if right <= left or bottom <= top:
        return None
    return float(page[top:bottom, left:right].mean())


def caption_boxes_from_words(
    words: list[tuple[str, float, float, float, float]],
) -> list[CaptionBox]:
    """Locate the three item 5 captions among a page's word boxes.

    ``words`` is (text, left, top, right, bottom) per word, in the pixels of the
    render the caller is about to sample. A caption of two words is matched as
    two adjacent words on the same line and reported as one box spanning both,
    because the check box sits to the left of the **first** of them.

    The first occurrence of each option wins. Item 5 is the only place the form
    prints these three together, and a later mention, in the certificate block or
    in an applicant's own text, is not item 5.
    """
    found: dict[str, CaptionBox] = {}
    lowered = [(text.strip(" .:,").casefold(), *box) for text, *box in words]
    for option, stems in OPTIONS.items():
        box = _match(lowered, stems)
        if box is not None:
            found[option] = CaptionBox(option=option, **box)
    return [found[option] for option in OPTIONS if option in found]


def _match(
    words: list[tuple[str, float, float, float, float]], stems: tuple[str, ...]
) -> dict[str, float] | None:
    """The first run of adjacent words matching these stems, as one box."""
    for start in range(len(words) - len(stems) + 1):
        run = words[start : start + len(stems)]
        if not all(text.startswith(stem) for (text, *_), stem in zip(run, stems, strict=True)):
            continue
        # Each entry is (text, left, top, right, bottom), so the geometry starts
        # at index 1. Named here rather than indexed at every use, because an
        # off-by-one into this tuple is a silent wrong answer rather than an
        # error: it reads a caption's text as its coordinate.
        lefts = [entry[1] for entry in run]
        tops = [entry[2] for entry in run]
        rights = [entry[3] for entry in run]
        bottoms = [entry[4] for entry in run]
        # Adjacent in reading order is not enough on its own: two words on
        # different lines can be consecutive. Requiring the run to share a
        # vertical band is what keeps "MALT" at the foot of one column and
        # "BEVERAGES" at the head of the next from reading as one caption.
        heights = [bottom - top for top, bottom in zip(tops, bottoms, strict=True)]
        if max(tops) - min(tops) > 0.5 * max(heights):
            continue
        return {
            "left": min(lefts),
            "top": min(tops),
            "right": max(rights),
            "bottom": max(bottoms),
        }
    return None


def word_boxes_from_ocr(page_png: bytes) -> list[tuple[str, float, float, float, float]]:
    """Read one rendered page's word boxes, for a page with no text layer.

    **A scan is the only path that pays for this.** Where the document has a text
    layer, the caption boxes come out of that layer exactly and for nothing, which
    is both cheaper and better evidence than a recognition step: see
    ``app.application_form._item_five_captions``. A scanned or photographed form
    has no text layer, so its captions have to be recognized, and this is the one
    place item 5 costs a Tesseract pass.

    The render is read as it is: no thresholding, no resize, no deskew. That is
    not a shortcut, it is a requirement. The boxes this returns are used to place
    a sample window on **these** pixels, and every one of those transforms would
    move the words relative to the image the sample is taken from.
    """
    timing.tesseract_read()
    with Image.open(io.BytesIO(page_png)) as image:
        data = pytesseract.image_to_data(image.convert("L"), lang="eng", output_type=Output.DICT)
    return [
        (
            str(text),
            float(data["left"][index]),
            float(data["top"][index]),
            float(data["left"][index]) + float(data["width"][index]),
            float(data["top"][index]) + float(data["height"][index]),
        )
        for index, text in enumerate(data.get("text", []))
        if str(text).strip() and float(data["conf"][index]) >= 0
    ]
