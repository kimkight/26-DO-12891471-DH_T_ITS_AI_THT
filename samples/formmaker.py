"""Render synthetic COLA application documents: PDF, fillable PDF, and image.

Shared by the backend tests so that no real applicant's label application has
to be committed to the repository. The test data policy in
docs/07_TEST_STRATEGY.md section 8 forbids real application data and personal
data in any fixture, and a filed TTB F 5100.31 carries a permit number, a
signature and a named person on every copy. Every value produced here is
invented, and the permit and serial numbers are deliberately not in a format
TTB issues.

Three documents are produced from one specification, because the parser has
three ways in and each has to be exercised on artwork it did not also produce:

* ``as_pdf_bytes`` writes a PDF whose text layer carries the lines given to it.
  This is what COLAs Online output and a Public COLA Registry printout are:
  digitally generated, so the characters are in the file rather than in the
  pixels.
* ``as_fillable_pdf_bytes`` writes a PDF with AcroForm fields carrying values,
  which is what an applicant's filled-in copy of the downloadable form is. The
  values are in the form fields; the text layer holds only the blank template.
* ``as_png_bytes`` draws the same lines as pixels, which is what a scan or a
  photograph of a printed form is. It carries no text layer at all.

``as_pdf_bytes`` also takes ``images``: raster artwork embedded into the file as
image XObjects on pages of their own, which is what a real filed application
carries. The applicant affixes the label artwork to the application, so the
values that are not items on the form are in those pictures rather than in the
text layer. See [ADR 0010](../docs/adr/0010-embedded-label-artwork.md).

Nothing here imports the application. It writes documents; it makes no claim
about what the parser should find in them.

The item captions are transcribed from TTB F 5100.31 (04/2023), fetched from
https://www.ttb.gov/system/files/images/pdfs/forms/f510031.pdf during
development. See docs/adr/0008-cola-form-as-application-input.md.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from samples.labelmaker import available_fonts

# US Letter at 72 points to the inch, which is what the real form is.
PAGE_WIDTH = 612
PAGE_HEIGHT = 792


@dataclass(frozen=True)
class ApplicationSpec:
    """One invented label application. Every value here is fictitious."""

    brand_name: str = "STONE'S THROW"
    fanciful_name: str = "Small Batch Reserve"
    beverage_type: str = "distilled spirits"
    # Not items on TTB F 5100.31 (04/2023). A Public COLA Registry printout
    # carries them; the paper form does not. Empty means the document does not
    # state them, which is the ordinary case for the paper form.
    class_type: str = ""
    class_type_code: str = ""
    alcohol_content: str = ""
    net_contents: str = ""
    serial_number: str = "ZZ-0001"
    plant_registry: str = "DSP-XX-00000"
    applicant: str = "EXAMPLE DISTILLING COMPANY, ANYTOWN, EX 00000"


def paper_form_lines(spec: ApplicationSpec) -> list[str]:
    """The application side of TTB F 5100.31 (04/2023), as text lines.

    Item 5 prints all three product types, because on the real form it is three
    checkboxes and the caption of an unticked box is printed just as the caption
    of a ticked one is. That is not a shortcoming of this fixture: it is the
    reason the text layer of a form cannot say which box was ticked, and the
    parser has to report the beverage type as not found from it.
    """
    lines = [
        "OMB No. 1513-0020",
        "DEPARTMENT OF THE TREASURY",
        "ALCOHOL AND TOBACCO TAX AND TRADE BUREAU",
        "APPLICATION FOR AND CERTIFICATION/EXEMPTION OF LABEL/BOTTLE APPROVAL",
        "PART I - APPLICATION",
        "1. REP. ID. NO. (If any)",
        "2. PLANT REGISTRY/BASIC PERMIT/BREWER'S NO. (Required)",
        spec.plant_registry,
        "3. SOURCE OF PRODUCT",
        "Domestic",
        "4. SERIAL NUMBER (Required)",
        spec.serial_number,
        "5. TYPE OF PRODUCT (Required)",
        "WINE",
        "DISTILLED SPIRITS",
        "MALT BEVERAGES",
        "6. BRAND NAME (Required)",
        spec.brand_name,
        "7. FANCIFUL NAME (If any)",
        spec.fanciful_name,
        "8. NAME AND ADDRESS OF APPLICANT AS SHOWN ON PLANT REGISTRY, BASIC",
        "PERMIT, OR BREWER'S NOTICE.",
        spec.applicant,
        "9. FORMULA",
        "10. GRAPE VARIETAL(S) Wine only",
        "11. WINE APPELLATION (If on label)",
        "12. PHONE NUMBER",
        "13. EMAIL ADDRESS",
        "14. TYPE OF APPLICATION (Check applicable box(es))",
        "a. CERTIFICATE OF LABEL APPROVAL",
        "15. SHOW ANY INFORMATION THAT IS BLOWN, BRANDED, OR EMBOSSED ON THE",
        "CONTAINER (e.g., net contents) ONLY IF IT DOES NOT APPEAR ON THE LABELS",
        "AFFIXED BELOW.",
    ]
    if spec.net_contents:
        lines.append(spec.net_contents)
    lines += [
        "16. DATE OF APPLICATION",
        "PART III - TTB CERTIFICATE",
        "19. DATE ISSUED",
        "TTB F 5100.31 (04/2023) PREVIOUS EDITIONS ARE OBSOLETE",
    ]
    return lines


def registry_printout_lines(spec: ApplicationSpec, *, captions: str = "compact") -> list[str]:
    """A Public COLA Registry detail page, as text lines.

    Key and value on one line, which is the shape a printed detail page has and
    the shape the paper form does not. It is the only one of the three that
    states a class or type designation, an alcohol content or a net contents,
    because those are not items on the form.

    Two caption styles, because printouts differ and the difference matters to
    the reader:

    * ``compact`` writes one ``CLASS/TYPE:`` line, with the code joined to the
      description by a dash where there is one.
    * ``descriptive`` writes the pair a real printout carries,
      ``Class/Type Code:`` and ``Class/Type Description:``. Those two lines are
      given in the capitalization the author read off a deployed-target printout
      on 2026-08-28; the rest of the page keeps this fixture's upper case.
    """
    if captions not in ("compact", "descriptive"):
        raise ValueError(f"unknown caption style: {captions}")

    class_type = spec.class_type
    if captions == "compact" and spec.class_type_code and class_type:
        class_type = f"{spec.class_type_code} - {class_type}"
    lines = [
        "TTB Public COLA Registry",
        "TTB ID: 00000000000000",
        "STATUS: APPROVED",
        f"SERIAL #: {spec.serial_number}",
        f"BRAND NAME: {spec.brand_name}",
        f"FANCIFUL NAME: {spec.fanciful_name}",
    ]
    if captions == "descriptive":
        if spec.class_type_code:
            lines.append(f"Class/Type Code: {spec.class_type_code}")
        if class_type:
            lines.append(f"Class/Type Description: {class_type}")
    elif class_type:
        lines.append(f"CLASS/TYPE: {class_type}")
    if spec.alcohol_content:
        lines.append(f"ALCOHOL CONTENT: {spec.alcohol_content}")
    if spec.net_contents:
        lines.append(f"NET CONTENTS: {spec.net_contents}")
    lines.append("ORIGIN: EXAMPLE STATE")
    return lines


# --------------------------------------------------------------------------
# Item 5's three check boxes, drawn (v1.2.0).
# --------------------------------------------------------------------------
#
# The three captions ``paper_form_lines`` already prints, with a square drawn to
# the left of each and one of them optionally filled. That is the shape of the
# real item 5, and it is the shape ``app.product_type`` samples: a box about a
# cap height and a half on a side, set a fraction of a cap height clear of the
# caption's first letter.
#
# **Nothing here is a coordinate the application knows.** The boxes are drawn
# from the same caption geometry the reader derives them from, so the fixture and
# the reader agree about where a box is for the same reason a real form and the
# reader do, rather than by sharing a constant.
PRODUCT_TYPE_OPTIONS = ("WINE", "DISTILLED SPIRITS", "MALT BEVERAGES")

# How dark a ticked box is drawn, on the 0 to 255 scale.
#
# **Chosen to reproduce the author's own measurement rather than to pass.** A
# real tick is a pen stroke or a printed cross covering part of the box, not a
# filled square, and a fixture that filled it solid black would clear a margin no
# real document has to clear. At 110 the reader measures the ticked box at 212
# against 233 and 235 for the two empty ones, which is within a few points of the
# 217.5 against 239.9 and 241.8 the author measured on her own filing.
TICK_GREY = 110


def _checkbox_geometry(
    caption_left: float, caption_top: float, cap_height: float
) -> tuple[float, float, float, float]:
    """The square to the left of one caption, as (left, top, right, bottom)."""
    size = cap_height * 1.4
    right = caption_left - cap_height * 0.4
    centre_y = caption_top + cap_height / 2
    return right - size, centre_y - size / 2, right, centre_y + size / 2


def as_pdf_with_product_type_boxes(
    lines: list[str],
    *,
    ticked: str | None,
    also_ticked: str | None = None,
    grey: int = TICK_GREY,
    font_size: int = 9,
) -> bytes:
    """A text-layer PDF whose item 5 boxes are drawn, with at most two ticked.

    ``ticked`` is one of ``PRODUCT_TYPE_OPTIONS`` or None for a form with no box
    filled. ``also_ticked`` fills a second one, which is the ambiguous document
    the reader has to refuse to answer from. ``grey`` is how dark the tick is
    drawn, so a test can put one either side of the reader's margin.
    """
    content = _content_stream(lines, font_size)
    boxes = _product_type_box_stream(lines, font_size, ticked, also_ticked, grey)
    return _assemble(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ).encode("ascii"),
            _stream_object(content + b"\n" + boxes),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        ],
        root=1,
    )


def _product_type_box_stream(
    lines: list[str], font_size: int, ticked: str | None, also_ticked: str | None, grey: int
) -> bytes:
    """Draw one square per item 5 option, filling the ticked ones.

    The caption positions are recomputed from the same leading and origin
    ``_content_stream`` lays the text out with, in PDF user space with the origin
    at the bottom left.
    """
    leading = font_size + 4
    parts: list[str] = []
    filled = {name for name in (ticked, also_ticked) if name}
    for index, line in enumerate(lines):
        if line not in PRODUCT_TYPE_OPTIONS:
            continue
        # _content_stream starts at PAGE_HEIGHT - 50 and moves down one leading
        # per line, so line n sits with its baseline at that origin minus n
        # leadings. The caption box top is one cap height above the baseline.
        baseline = PAGE_HEIGHT - 50 - index * leading
        cap_height = font_size * 0.7
        left, top, right, bottom = _checkbox_geometry(40, -(baseline + cap_height), cap_height)
        # Back into PDF space, where y grows upward.
        top, bottom = -top, -bottom
        parts.append("0 0 0 RG 0.6 w")
        parts.append(f"{left:.2f} {bottom:.2f} {right - left:.2f} {top - bottom:.2f} re S")
        if line in filled:
            inset = (right - left) * 0.15
            parts.append(f"{grey / 255:.3f} g")
            parts.append(
                f"{left + inset:.2f} {bottom + inset:.2f} "
                f"{right - left - 2 * inset:.2f} {top - bottom - 2 * inset:.2f} re f"
            )
            parts.append("0 g")
    return "\n".join(parts).encode("ascii")


def as_scanned_pdf_bytes(png: bytes) -> bytes:
    """One page that is nothing but the given image, at the image's own aspect.

    This is a scanned form: no text layer anywhere, one raster page. It differs
    from ``as_pdf_bytes(..., images=[...])`` in two ways that matter to a reader
    which samples pixels. There is no text page in front of it, so page 1 is the
    scan; and the image is fitted to the page rather than stretched across it, so
    a square drawn on the scan is still square on the render. A fixture that
    stretched it would be testing how the reader copes with a distortion a
    scanner does not produce.
    """
    jpeg, width, height = _as_jpeg(png)
    scale = min(PAGE_WIDTH / width, PAGE_HEIGHT / height)
    drawn_width, drawn_height = width * scale, height * scale
    left = (PAGE_WIDTH - drawn_width) / 2
    bottom = (PAGE_HEIGHT - drawn_height) / 2
    content = (
        f"q\n{drawn_width:.2f} 0 0 {drawn_height:.2f} {left:.2f} {bottom:.2f} cm\n/Im0 Do\nQ"
    ).encode("ascii")
    return _assemble(
        [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                "/Resources << /XObject << /Im0 5 0 R >> >> /Contents 4 0 R >>"
            ).encode("ascii"),
            _stream_object(content),
            (
                f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
                "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length "
                f"{len(jpeg)} >>\nstream\n"
            ).encode("ascii")
            + jpeg
            + b"\nendstream",
        ],
        root=1,
    )


def as_png_with_product_type_boxes(
    lines: list[str], *, ticked: str | None, grey: int = TICK_GREY, font_size: int = 22
) -> bytes | None:
    """The same page drawn as pixels, with no text layer. None if no font.

    This is the scan: the captions have to be recognized before the boxes can be
    placed, which is the one path item 5 costs a Tesseract read on.
    """
    fonts = available_fonts()
    if fonts is None:
        return None
    _, regular = fonts
    font = ImageFont.truetype(regular, font_size)
    margin = 60
    leading = int(font_size * 1.6)
    height = margin * 2 + leading * len(lines)
    image = Image.new("RGB", (1700, max(height, 400)), "white")
    draw = ImageDraw.Draw(image)
    cap_height = font_size * 0.72
    for index, line in enumerate(lines):
        top = margin + index * leading
        draw.text((margin, top), line, font=font, fill="black")
        if line not in PRODUCT_TYPE_OPTIONS:
            continue
        left, box_top, right, bottom = _checkbox_geometry(margin, top, cap_height)
        draw.rectangle((left, box_top, right, bottom), outline="black", width=2)
        if line == ticked:
            inset = (right - left) * 0.15
            draw.rectangle(
                (left + inset, box_top + inset, right - inset, bottom - inset),
                fill=(grey, grey, grey),
            )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def as_pdf_bytes(
    lines: list[str], *, font_size: int = 9, images: list[bytes] | None = None
) -> bytes:
    """Write the lines into a PDF with a real text layer, plus any images given.

    Helvetica is one of the fourteen fonts every PDF reader carries, so nothing
    has to be embedded and the file has no dependency on a font being installed.

    ``images`` are PNG bytes, each embedded as an image XObject on a page of its
    own after the text page. That is the shape a real filed application has: the
    applicant affixes the label artwork, so the application carries pictures of
    the labels alongside the typed items. They are re-encoded to JPEG and
    embedded with ``/DCTDecode``, which every PDF reader decodes without an
    external filter, so the fixture depends on nothing but Pillow.
    """
    pages = [_text_page_content(lines, font_size)]
    embedded = [_as_jpeg(image) for image in (images or [])]

    # Object numbers are assigned by position in the list below, from 1.
    # 1 catalog, 2 pages, 3 font, then one page object and one content stream
    # per page, then one XObject per embedded image.
    font_number = 3
    first_page = 4
    page_count = 1 + len(embedded)
    first_image = first_page + page_count * 2
    page_refs = [f"{first_page + index * 2} 0 R" for index in range(page_count)]

    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        ("<< /Type /Pages /Kids [" + " ".join(page_refs) + f"] /Count {page_count} >>").encode(
            "ascii"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]

    for index in range(page_count):
        content_number = first_page + index * 2 + 1
        if index == 0:
            resources = f"<< /Font << /F1 {font_number} 0 R >> >>"
        else:
            resources = f"<< /XObject << /Im0 {first_image + index - 1} 0 R >> >>"
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources {resources} /Contents {content_number} 0 R >>"
            ).encode("ascii")
        )
        objects.append(_stream_object(pages[index] if index == 0 else _image_page_content()))

    for jpeg, width, height in embedded:
        objects.append(
            (
                f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} "
                "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length "
                f"{len(jpeg)} >>\nstream\n"
            ).encode("ascii")
            + jpeg
            + b"\nendstream"
        )
    return _assemble(objects, root=1)


def _as_jpeg(png: bytes) -> tuple[bytes, int, int]:
    """Re-encode PNG bytes as JPEG, which is what ``/DCTDecode`` embeds.

    Quality 95 rather than the default, because the point of embedding the
    artwork is that it keeps the resolution the page render loses, and a fixture
    that quietly degraded it would test something other than what ships.
    """
    image = Image.open(io.BytesIO(png)).convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=95)
    return buffer.getvalue(), image.width, image.height


def _image_page_content() -> bytes:
    """Draw the page's single image XObject across the whole page."""
    return (f"q\n{PAGE_WIDTH} 0 0 {PAGE_HEIGHT} 0 0 cm\n/Im0 Do\nQ").encode("ascii")


def _stream_object(content: bytes) -> bytes:
    return (
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream"
    )


def as_fillable_pdf_bytes(spec: ApplicationSpec, *, font_size: int = 9) -> bytes:
    """Write a PDF whose values live in AcroForm fields, not in the text layer.

    This is an applicant's filled-in copy of the downloadable form. The text
    layer holds the blank template's captions only, which is why the parser
    reads the field values rather than the page. The product type is a radio
    group of three widgets sharing one field name, exactly as it is on the real
    form, where the export values are ``Wine``, ``Spirits`` and ``Malt``.
    """
    export = {"wine": "Wine", "distilled spirits": "Spirits", "malt beverage": "Malt"}[
        spec.beverage_type
    ]
    captions = [
        "5. TYPE OF PRODUCT (Required)",
        "WINE",
        "DISTILLED SPIRITS",
        "MALT BEVERAGES",
        "6. BRAND NAME (Required)",
        "7. FANCIFUL NAME (If any)",
        "TTB F 5100.31 (04/2023) PREVIOUS EDITIONS ARE OBSOLETE",
    ]
    content = _content_stream(captions, font_size)

    # Object numbers are assigned by position in this list, from 1.
    text_widgets = [
        ("6. BRAND NAME (Required)", spec.brand_name, 300),
        ("7. FANCIFUL NAME (If any)", spec.fanciful_name, 280),
    ]
    first_widget = 6
    widget_refs = [f"{first_widget + index} 0 R" for index in range(len(text_widgets))]
    radio_parent = first_widget + len(text_widgets)
    kid_refs = [f"{radio_parent + 1 + index} 0 R" for index in range(3)]

    objects = [
        (
            "<< /Type /Catalog /Pages 2 0 R /AcroForm << /Fields ["
            + " ".join([*widget_refs, f"{radio_parent} 0 R"])
            + "] /DA (/Helv 0 Tf 0 g) >> >>"
        ).encode("ascii"),
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
            "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R /Annots ["
            + " ".join([*widget_refs, *kid_refs])
            + "] >>"
        ).encode("ascii"),
        b"<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for name, value, top in text_widgets:
        objects.append(
            (
                "<< /Type /Annot /Subtype /Widget /FT /Tx /P 3 0 R /F 4 "
                f"/Rect [200 {top} 560 {top + 14}] /T ({_escape(name)}) "
                f"/V ({_escape(value)}) /DA (/Helv 9 Tf 0 g) >>"
            ).encode("ascii")
        )
    objects.append(
        (
            "<< /FT /Btn /Ff 32768 /T (Check Box22) "
            f"/V /{export} /Kids [" + " ".join(kid_refs) + "] >>"
        ).encode("ascii")
    )
    for index, option in enumerate(("Wine", "Spirits", "Malt")):
        state = option if option == export else "Off"
        top = 400 - index * 12
        objects.append(
            (
                "<< /Type /Annot /Subtype /Widget /Parent "
                f"{radio_parent} 0 R /P 3 0 R /F 4 /Rect [150 {top} 162 {top + 10}] "
                f"/AS /{state} /AP << /N << /{option} 4 0 R /Off 4 0 R >> >> >>"
            ).encode("ascii")
        )
    return _assemble(objects, root=1)


def as_png_bytes(lines: list[str], *, font_size: int = 22) -> bytes | None:
    """Draw the lines as pixels, with no text layer. None if no font is present.

    Callers skip rather than guess when this returns None, for the reason
    ``samples.labelmaker.available_fonts`` gives: Pillow's built-in bitmap font
    produces glyphs Tesseract cannot read, so a test that fell back to it would
    report an OCR failure that is really a font failure.
    """
    fonts = available_fonts()
    if fonts is None:
        return None
    _, regular = fonts
    font = ImageFont.truetype(regular, font_size)
    margin = 60
    leading = int(font_size * 1.6)
    height = margin * 2 + leading * len(lines)
    image = Image.new("RGB", (1700, max(height, 400)), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((margin, margin + index * leading), line, font=font, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _escape(text: str) -> str:
    """Escape the three characters that are syntax inside a PDF string."""
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _text_page_content(lines: list[str], font_size: int) -> bytes:
    """The text page's content stream. A thin name for what ``as_pdf_bytes`` needs."""
    return _content_stream(lines, font_size)


def _content_stream(lines: list[str], font_size: int) -> bytes:
    leading = font_size + 4
    parts = ["BT", f"/F1 {font_size} Tf", f"{leading} TL", f"1 0 0 1 40 {PAGE_HEIGHT - 50} Tm"]
    for line in lines:
        parts.append(f"({_escape(line)}) Tj")
        parts.append("T*")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", "replace")


def _assemble(objects: list[bytes], *, root: int) -> bytes:
    """Serialize numbered objects with a cross-reference table and a trailer."""
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {root} 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)
