# ADR 0016: The form is a picture as well as a text layer, so item 5 is read from the page

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-31 |
| Author | Kimberly D. Kight |
| Decision reference | Amends [ADR 0008](0008-cola-form-as-application-input.md) and assumption A-17; applies [ADR 0010](0010-embedded-label-artwork.md)'s lesson a second time; FR-11; nothing in FR-1 through FR-7 changes |

## Context

The author asked whether beverage type is a field on the application.

**It is.** Item 5 of TTB F 5100.31 (04/2023), "TYPE OF PRODUCT (Required)", three
check boxes: WINE, DISTILLED SPIRITS, MALT BEVERAGES. It is one of the two
required items on the first half of the form.

The tool has been leaving it blank on almost every filing. There are two paths
that could answer it and both were exhausted:

1. **An AcroForm radio group**, on an applicant's unflattened copy of the
   downloadable form. That path works and is unchanged.
2. **The text layer**, on everything else. It cannot work, and
   `_sole_product_type` says why in its own docstring: a text layer prints the
   caption of an unticked box exactly as it prints the caption of a ticked one,
   so a document naming all three has said nothing about which was chosen.
   Refusing to guess from it was the right call and remains so.

What was never tried is the third place the answer is: **the pixels**. The tool
already renders the document's pages (`_render_page`, added for the OCR
fallback). On the author's own filing, rendered at scale 2.0, sampling the three
item 5 check box regions:

| item 5 option | mean luminance |
| --- | --- |
| WINE | 239.9 |
| **DISTILLED SPIRITS** | **217.5** |
| MALT BEVERAGE | 241.8 |

A 22.4 point separation, on deliberately loose coordinates. The two boxes that
are the same differ from each other by 1.9. Item 3, "SOURCE OF PRODUCT", shows
the same pattern with "Imported" ticked.

**This is the same lesson as the embedded label artwork, in a second place.**
ADR 0010 found three of the five compared values sitting inside pictures in a
file the parser was reading only the text of. This is the same defect one item
over: **the form is a picture as well as a text layer, and the tool has to look
at both.** That is the through-line of the last three defect sessions, and it is
worth stating plainly rather than fixing case by case:

| session | what was invisible | where it actually was |
| --- | --- | --- |
| ADR 0010 | alcohol content, net contents, class or type | pictures of the label, embedded in the PDF |
| ADR 0015 | the brand name and the class or type on the label | the label text, already read, never searched |
| this one | the type of product | the form's own page, never sampled |

## Decision

**Read item 5's boxes off the rendered page.**

### 1. The boxes are located from their own captions, never from a coordinate

The three captions are found on the page, and each check box is taken to be the
square immediately to the left of its caption. **No pixel coordinate is hard
coded anywhere**, and the constraint is the author's: the form has editions, this
tool renders at a scale derived from the page size and a setting, and a
coordinate measured on one render of one edition is a number that happens to be
right once.

The captions are found in one of two ways, in this order:

- **From the text layer**, where the file has one. PDFium reports a character box
  per character, so the caption's position is exact, costs nothing, and went
  through no recognition step. This is the path the author's own filing takes and
  it is strictly better evidence than the alternative, for the same reason ADR
  0010 puts a text layer ahead of a picture everywhere else.
- **From OCR word boxes**, on a page that has no text layer: a scan, a photograph
  of the form, or a rasterised PDF. This is the one input item 5 costs a Tesseract
  pass on, and it is gated twice: on the page render having already read the
  "TYPE OF PRODUCT" caption, so a document that is not this form never pays it,
  and on nothing else having answered, so a filled AcroForm never pays it either.

Everything geometric is expressed in **caption text heights**, so the same
arithmetic holds at any scale and any type size.

### 2. The sample window is deliberately loose

The window is a square reaching left from just short of the caption, 2.4 caption
heights on a side, comfortably containing a box of anything from about one to
about two caption heights.

**Loose rather than tight, and the reason is a measurement.** A tight crop on the
box's interior gives a bigger number when it lands exactly and a wrong answer when
it does not. On a fixture rendered small enough that a caption is twelve pixels
high, a **one pixel** difference in where OCR put a caption's left edge moved a
tight window onto one box's printed rule and off another's, and produced a fifteen
point difference between two boxes that were **both empty**. A window that
contains the whole box contains both rules for every option, so the baseline is
the same for all three and only a tick moves it. The author's own measurement was
taken on "deliberately loose coordinates" and separated by 22 points, which is the
same finding arrived at from the other side.

The window stops short of the caption rather than growing towards it: the three
captions begin with three different letters, and pulling caption ink into the
sample would put a difference between the options that has nothing to do with
which one is ticked.

### 3. The margin, and why it is 12.0

**The darkest box is reported as ticked only when it is at least
`PRODUCT_TYPE_MARGIN` luminance points darker than the next darkest**, on the 0
to 255 scale. Since the next darkest is by definition no darker than the third,
clearing the margin against it clears it against both.

The number is set from both ends of the measurement, and neither end is a guess:

| | measured | source |
| --- | --- | --- |
| signal | 22.4 points | the author's own filing, a real tick |
| signal | 20.5 points | the fixture's tick on a text-layer PDF |
| signal | 21.5 points | the same page as a scan |
| noise | 1.9 points | the author's two **empty** boxes |
| noise | 0.5 to 2.8 points | the fixtures' empty boxes, over four renders |

**12.0 sits between them and not in the middle of them.** It is about half the
observed signal, so a tick half as dark as a real one is still read, and about
six times the worst observed noise, so a difference produced by paper texture, a
heavier printed rule or a scanner's uneven illumination is not. `TestTheMargin`
asserts both sides of it by varying how dark the fixture draws the tick.

Erring towards the noise floor would be the expensive direction to be wrong in.
FR-1's rule is that a value the tool cannot identify is reported as not found
rather than guessed, and a wrongly-read product type would silently select the
wrong numeric rule.

### 4. Two close, or none filled, is not determined

Both come back as not determined and the agent chooses, exactly as they do today,
because on this evidence they are the same situation: nothing about the page says
which one was chosen. The reason says the boxes **were sampled** and did not
settle it, which is a different thing for an agent to know from "this document did
not name one type".

### 5. Precedence: a form field wins, a text inference does not

An AcroForm radio group is a statement the file makes and nothing was recognized
to get it, so it still wins. A tick read off the page is a recognition, and it
does not overrule that, exactly as embedded artwork does not overrule a text
layer.

`_sole_product_type` is neither, and this is the one precedence that changes. It
is an inference from absence: the text names one of the three types and not the
other two, so it is taken to be stating one rather than offering a choice. That
holds on a Registry printout and **it fails on a scan**, where OCR dropping two
captions produces the same evidence and the wrong answer. A scanned form with
nothing ticked used to come back as whichever caption OCR happened to read
cleanly. Sampling the boxes is direct evidence of the thing being inferred, so it
supersedes the inference, in both directions: it fills the value where a box
stands out, and it clears the value where the boxes were sampled and none did.

### 6. What does not change

**The beverage type is still never compared against the label.** A label does not
print a form answer, so the embedded artwork still cannot supply it and
`ARTWORK_FIELDS` still excludes it. What it does is select which numeric rule
runs, A-12's proof cross-check for spirits or A-13's ranges for wine, and the
result panel already names the rule that ran.

**It is surfaced for confirmation and stays editable**, like every other parsed
value (FR-11, FR-13). It carries its own provenance chip, "Ticked box on the
form", separate from both the form-text chip and the label-artwork one: a value
measured off pixels can be misread in a way a text-layer value cannot, and the
form's own page is not the label artwork.

## Alternatives rejected

### Hard-coding the item 5 coordinates for the 04/2023 edition

**Rejected on the author's own instruction, and she is right.** The form itself
says previous editions are obsolete without saying what they contained, so other
editions exist and may lay item 5 out differently; this tool renders at a scale
derived from the page size and `TTB_OCR_LONG_EDGE_PX`, so the same edition
produces different pixels under a different setting; and a scan arrives at
whatever resolution the scanner was set to. A coordinate would be right on one
document and silently wrong on the next.

### Reading the tick with OCR rather than by luminance

**Rejected because a tick is not text.** Tesseract asked to read a check box
returns whatever glyph a cross or a pen stroke most resembles, at low confidence,
and a filled box returns nothing at all. The question is "is there more ink in
this box than in the other two", and that is a measurement rather than a
recognition. It is also free: the page is rendered either way.

### Trusting `_sole_product_type` on a scan

**Rejected because it is demonstrably wrong there**, and the test that pins it is
`test_a_scan_with_nothing_ticked_is_not_determined`. The inference is sound on a
document whose text genuinely names one type and unsound on one whose OCR lost
two captions, and nothing in the text distinguishes those two cases.

## Consequences

**Item 5 is answered on a flattened, printed or scanned filing**, which is the
ordinary case and the one the tool has always been silent on.

**A scanned form with nothing ticked stops being answered wrongly.** That is a
false positive removed, not a feature added, and it is the more valuable half.

**The cost is bounded and mostly zero.** A document with a text layer pays a page
render and some arithmetic, and no Tesseract pass at all;
`test_the_captions_are_located_from_the_text_layer_at_no_ocr_cost` asserts that.
A document without one pays exactly one pass, on one page, and only after its own
text has already named item 5. The new `item_five_ocr_ms` phase reports it
(NFR-1).

**The failure mode is the safe one.** Where the captions cannot be found, where a
box falls off the page, or where the separation falls short, the reading is not
determined, the agent chooses as they do today, and the reason says which of those
happened.

**The residual risk is an edition that lays item 5 out differently**, with the box
somewhere other than immediately left of its caption. The sample window would then
land on paper for all three options, the separation would collapse, and the
reading would be not determined. That is the honest failure and it is the one this
was designed to fail into. It is recorded against A-17's existing edition caveat
and OQ-22 rather than claimed away.
