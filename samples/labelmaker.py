"""Render synthetic label artwork with Pillow.

Shared by samples/generate_samples.py, scripts/measure.py, and the backend
integration test, so that all three exercise the same artwork and no label
image has to be committed to the repository. samples/README.md explains why
images are git-ignored: label artwork can carry third-party trade dress and the
assignment grants no rights to redistribute real labels.

Nothing here imports the application. It draws pixels; it makes no claim about
what the pipeline should find in them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Candidate font paths, in preference order. DejaVu ships with Debian, Ubuntu
# and the GitHub Actions runner images; Liberation is the usual alternative.
FONT_CANDIDATES = (
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ),
    (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ),
    (
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ),
)

CANVAS = (1000, 1500)


def available_fonts() -> tuple[str, str] | None:
    """Return a (bold, regular) font pair that exists on this machine, or None.

    Callers skip rather than guess when this returns None: rendering with
    Pillow's built-in bitmap font produces glyphs Tesseract cannot read, so a
    test that fell back to it would report an OCR failure that is really a font
    failure.
    """
    for bold, regular in FONT_CANDIDATES:
        if Path(bold).is_file() and Path(regular).is_file():
            return bold, regular
    return None


@dataclass
class LabelSpec:
    """The text to print on one label and how to print it."""

    filename: str
    brand_name: str
    class_type: str
    alcohol_content: str
    net_contents: str | None
    warning: str | None
    producer: str = "Distilled and bottled by the named producer"
    rotate_degrees: float = 0.0
    low_contrast: bool = False
    notes: str = ""
    beverage_type: str = "distilled spirits"
    application: dict[str, str] = field(default_factory=dict)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int):
    """Greedy word wrap against the rendered width of the string."""
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word])
        if draw.textlength(candidate, font=font) <= width and current:
            current.append(word)
        elif not current:
            current = [word]
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines


def render(spec: LabelSpec) -> Image.Image:
    """Draw one label. Type sizes descend from the brand name deliberately.

    Real labels set the brand name in the largest type on the face, which is the
    property app/parse.py uses to tell it from the class or type designation.
    Keeping that relationship here is what makes the sample set a fair test of
    that heuristic rather than a rigged one.
    """
    fonts = available_fonts()
    if fonts is None:
        raise RuntimeError("No usable TrueType font was found on this machine.")
    bold_path, regular_path = fonts

    background = (232, 232, 232) if spec.low_contrast else (255, 255, 255)
    ink = (120, 120, 120) if spec.low_contrast else (0, 0, 0)
    image = Image.new("RGB", CANVAS, background)
    draw = ImageDraw.Draw(image)

    brand_font = ImageFont.truetype(bold_path, 96)
    class_font = ImageFont.truetype(regular_path, 48)
    detail_font = ImageFont.truetype(regular_path, 34)
    producer_font = ImageFont.truetype(regular_path, 22)
    warning_font = ImageFont.truetype(regular_path, 26)

    margin = 70
    width = CANVAS[0] - 2 * margin
    y = 120

    for line in _wrap(draw, spec.brand_name, brand_font, width):
        draw.text((margin, y), line, font=brand_font, fill=ink)
        y += 120
    y += 30

    for line in _wrap(draw, spec.class_type, class_font, width):
        draw.text((margin, y), line, font=class_font, fill=ink)
        y += 64
    y += 40

    draw.text((margin, y), spec.alcohol_content, font=detail_font, fill=ink)
    y += 60
    if spec.net_contents:
        draw.text((margin, y), spec.net_contents, font=detail_font, fill=ink)
        y += 60
    y += 20

    draw.text((margin, y), spec.producer, font=producer_font, fill=ink)
    y += 60

    if spec.warning:
        # Explicit line breaks in the warning are honoured rather than reflowed.
        # A real bottle sets the warning in a column a few words wide and
        # hyphenates to fill it, and the only way to render that faithfully is
        # to let the caller say where the lines break. Everything else still
        # wraps to the label width, so the twelve committed specs are unchanged.
        for paragraph in spec.warning.split("\n"):
            for line in _wrap(draw, paragraph, warning_font, width):
                draw.text((margin, y), line, font=warning_font, fill=ink)
                y += 36

    if spec.rotate_degrees:
        image = image.rotate(spec.rotate_degrees, expand=True, fillcolor=background)
    return image


def render_png_bytes(spec: LabelSpec) -> bytes:
    """Render to PNG bytes, for callers that never want a file on disk."""
    import io

    buffer = io.BytesIO()
    render(spec).save(buffer, format="PNG")
    return buffer.getvalue()


# --------------------------------------------------------------------------
# Colour artwork (v1.1.0).
# --------------------------------------------------------------------------

# The three inks and the ground of a label printed in more than two tones.
#
# Chosen so that the three text classes fall into three luminance bands rather
# than two, which is the property that breaks a single global threshold and the
# reason app.ocr reads the colour image. On a green ground of luminance 96:
# the warning is near-black on a cream panel, the brand and the body copy are
# near-white directly on the ground, and the alcohol content and net contents
# are a red of luminance 102, which is to say all but isoluminant with the
# ground behind it and separable from it by hue alone.
COLOUR_GROUND = (60, 120, 70)
COLOUR_PANEL = (238, 236, 226)
COLOUR_DARK_INK = (16, 20, 18)
COLOUR_LIGHT_INK = (250, 250, 245)
COLOUR_CHROMA_INK = (200, 60, 60)

COLOUR_CANVAS = (1400, 1200)

# Body copy, and it is not decoration. Tesseract's orientation detection needs
# a paragraph of ordinary prose to answer confidently: without this block it
# reports the script as Japanese and returns a confidence of 1.5, and with it
# the script is Latin and the confidence is around 9. A fixture built to test
# the colour arm should not also be testing the orientation floor, so this is
# here to keep the two apart.
COLOUR_BODY_COPY = (
    "Distilled and bottled by the named producer in Oaxaca, Mexico. Imported by "
    "the named importer. Each village produces a mezcal of its own character, "
    "and this bottling is drawn from a single village and a single family of "
    "producers."
)


@dataclass
class ColourLabelSpec:
    """The text to print on one multi-tone label.

    Deliberately a separate type from ``LabelSpec`` rather than a flag on it.
    The twelve committed sample specs describe a black-on-white label and the
    accuracy tier's expectations are written against exactly that rendering;
    adding a colour mode to the same renderer would put a branch inside the
    thing those expectations are measured on.
    """

    brand_name: str = "DEL MAGUEY"
    class_type: str = "SINGLE VILLAGE MEZCAL"
    alcohol_content: str = "42% ALC BY VOL"
    net_contents: str = "750 ML"
    warning: str = ""
    body_copy: str = COLOUR_BODY_COPY


def render_colour(spec: ColourLabelSpec) -> Image.Image:
    """Draw one label in three inks on one ground.

    The ink each element is printed in is the point of the fixture, so it is
    stated here rather than varied: the brand, the class or type and the body
    copy are light on the dark ground, the warning is dark on a light panel, and
    the alcohol content and net contents are in the chroma ink that a grayscale
    conversion collapses into the ground behind them.
    """
    fonts = available_fonts()
    if fonts is None:
        raise RuntimeError("No usable TrueType font was found on this machine.")
    bold_path, regular_path = fonts

    width, height = COLOUR_CANVAS
    image = Image.new("RGB", (width, height), COLOUR_GROUND)
    draw = ImageDraw.Draw(image)

    brand_font = ImageFont.truetype(bold_path, 96)
    class_font = ImageFont.truetype(regular_path, 52)
    detail_font = ImageFont.truetype(bold_path, 46)
    body_font = ImageFont.truetype(regular_path, 26)
    warning_font = ImageFont.truetype(regular_path, 24)

    margin = 60
    text_width = width - 2 * margin
    y = 50

    draw.text((margin, y), spec.brand_name, font=brand_font, fill=COLOUR_LIGHT_INK)
    y += 128
    draw.text((margin, y), spec.class_type, font=class_font, fill=COLOUR_LIGHT_INK)
    y += 92
    draw.text((margin, y), spec.alcohol_content, font=detail_font, fill=COLOUR_CHROMA_INK)
    y += 68
    draw.text((margin, y), spec.net_contents, font=detail_font, fill=COLOUR_CHROMA_INK)
    y += 80

    for line in _wrap(draw, spec.body_copy, body_font, text_width):
        draw.text((margin, y), line, font=body_font, fill=COLOUR_LIGHT_INK)
        y += 34
    y += 20

    if spec.warning:
        lines = _wrap(draw, spec.warning, warning_font, text_width - 40)
        panel_height = len(lines) * 32 + 40
        draw.rectangle([margin, y, width - margin, y + panel_height], fill=COLOUR_PANEL)
        y += 20
        for line in lines:
            draw.text((margin + 20, y), line, font=warning_font, fill=COLOUR_DARK_INK)
            y += 32

    return image


def render_colour_png_bytes(spec: ColourLabelSpec, *, turned_degrees: int = 0) -> bytes:
    """Render to PNG bytes, optionally turned clockwise by a quarter-turn.

    PNG rather than JPEG so that the pixels a test asserts on are the pixels
    that were drawn: a lossy encoder would put its own chroma into an image
    whose whole subject is chroma.
    """
    import io

    image = render_colour(spec)
    if turned_degrees % 360:
        # Pillow turns counter-clockwise, and every rotation in this codebase is
        # stated clockwise, which is Tesseract's convention.
        image = image.rotate(-turned_degrees, expand=True)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
