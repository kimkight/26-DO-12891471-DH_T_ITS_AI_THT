# ADR 0010: The COLA document carries its own label artwork, and it is read

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-29 |
| Author | Kimberly D. Kight |
| Decision reference | Extends FR-11 and [ADR 0008](0008-cola-form-as-application-input.md); amends assumption A-17; supplies the label side the one-upload change that follows it depends on; leaves [ADR 0009](0009-batch-cola-documents.md) intact |

## Context

The author uploaded a real COLA document to the deployed v1.0.1 build on
2026-08-29: TTB Form 5100.31, OMB No. 1513-0020, three pages. **Two of the five
fields reconciled.** The diagnosis is not a guess, and it was made against the
file itself.

- The brand name and the class or type designation came out of the PDF's
  embedded text layer. Both correct.
- The alcohol content and the net contents are genuinely absent from the form's
  text layer, exactly as assumption A-17 already says: they are not items on
  TTB F 5100.31 (04/2023) at all.
- **But they are not absent from the document.** Pages 2 and 3 each carry an
  embedded raster image, and page 3 is the complete flat label artwork at
  1750 by 1150 pixels. It carries `DEL MAGUEY`, `VIDA SINGLE VILLAGE MEZCAL`,
  `42% ALC BY VOL`, `750 ML`, and the full horizontal GOVERNMENT WARNING.
- The parser never rasterized or extracted those images, so it never saw the
  values that were sitting inside the file it had been handed.
- OCR of that page 3 artwork at 2x reads the government warning with exactly one
  character wrong, `MPAIRS` for `IMPAIRS`; the brand name, the class or type,
  the alcohol content and the net contents all read.
- The beverage type is item 5's three check boxes. All three captions print in
  the text layer, so a tick cannot be read from text alone. ADR 0008 already
  records that, and nothing here changes it: a label does not print a form
  answer, so the artwork cannot supply it either.

That last point about the one wrong character is the reason FR-5's near-miss
routing exists; it is decided separately and is not this ADR's subject.

**Why the artwork is there at all.** The applicant affixes the label artwork to
the application. That is what item 15 on the form is written around: it asks the
applicant to "SHOW ANY INFORMATION THAT IS BLOWN, BRANDED, OR EMBOSSED ON THE
CONTAINER (e.g., net contents) ONLY IF IT DOES NOT APPEAR ON THE LABELS AFFIXED
BELOW." [Source: TTB F 5100.31 (04/2023), item 15, transcribed from the
downloaded form; see A-17.] The form's own instruction says the labels are
affixed to it. A filed COLA is therefore a document whose typed part is thin and
whose pictures carry most of what this tool compares.

## Decision

**Extract every embedded raster image from an uploaded COLA document, read the
ones large enough to be label artwork through the existing label OCR pipeline,
and use what they say to fill application-side values the text layer left empty.
The largest such image also becomes the label side of the check when the agent
supplied no photograph of their own.**

### Precedence, in one line

**Typed by the agent, then the document's text layer or form fields, then the
embedded artwork, then absent.**

Artwork never overrides text. A value the file itself states is read; a value
recognized off a picture is guessed at by an OCR engine, and the two are not
equal evidence. A typed value beats both, unchanged from ADR 0008: an agent who
corrects a field has looked and disagreed.

The response says which of the four each field came from, per field, in
`application_value_source` and in the per-value `source` on the parsed
application block. The interface shows it, and shows the caveat on the artwork
case specifically, because that is the one that can be misread.

### The size floor

An image survives only if **both** halves are met:

| Half | Default | What it rejects |
| --- | --- | --- |
| Shortest edge at least `TTB_MIN_ARTWORK_EDGE_PX` | 400 px | A long thin barcode or signature strip, whatever its area |
| Total pixels at least `TTB_MIN_ARTWORK_PIXELS` | 250,000 px, a 500 by 500 square | A small square seal or logo |

The numbers are stated as a judgement, not derived from a measurement, and they
are settings so an operator can move them (NFR-11). The basis: agency seals,
barcodes and signature blocks on a filed form are small, and label artwork is
not. The author's own document carries its artwork at 1750 by 1150, which is
2.0 megapixels, eight times the area floor. Nothing in the repository measures
the distribution of embedded image sizes across real filings, because the
repository holds no real filings; that is [OQ-24](../OPEN_QUESTIONS.md#oq-24).

At most `TTB_MAX_ARTWORK_IMAGES` surviving images are read, four by default,
because each one costs a full OCR read. Every page is searched, not only the
pages read for text: `TTB_MAX_DOCUMENT_PAGES` bounds how much text is read and
says nothing about where the pictures are, and on the author's document the
artwork is on page 3.

### The pipeline is the label pipeline, unchanged

Each surviving image goes through `app.ocr.extract_text` with its defaults, so
the v1.0.1 orientation decision and the preprocessed-against-plain best-of both
apply exactly as they do to a photograph, and `app.parse.parse_fields` locates
the fields exactly as it does on a label. The embedded artwork is flat, which is
the input that pipeline handles well; that is the whole reason this is worth
doing, and it is the opposite of the curved-bottle case in
[02_PROJECT_SCOPE.md](../02_PROJECT_SCOPE.md) section 3.

### The honest limitation, written down

**Comparing a label extracted from the application against the application it
came from is a self-consistency check, not an independent verification.** It
proves the artwork on file carries the mandatory elements and that they agree
with the typed form data. It does not prove anything about a bottle. Verifying
the physical bottle against the filing still needs a photograph of the physical
bottle.

That sentence is in three places rather than one: in the parser's own notes, in
the response as `self_consistency_note` whenever `label_source` is
`application_artwork`, and once on screen above the result. A limitation that
lives only in an ADR is a limitation nobody reads.

## Alternatives considered

### Alternative A: rasterize each page at a fixed DPI and read the whole page

Rejected on two grounds, both of which are properties of the input rather than
preferences.

**It loses resolution the artwork already has.** `_render_page` scales a whole
page so that its long edge is `TTB_OCR_LONG_EDGE_PX`, 1600 by default. Artwork
occupying a third of a page comes out at roughly a third of that, well under the
1750 by 1150 the author's file actually holds. Reading a downsampled copy of a
picture the file carries at full size is paying an accuracy cost for nothing.

**It reads the form's own text as if it were label text.** A page render hands
Tesseract the printed captions, the item numbers and the applicant block along
with the label. `app.parse` locates the brand name by type size, so the largest
text on the rendered page competes with the largest text on the label, and the
government warning search would run over a page containing both the label's
warning and whatever the form prints. Extracting the image gives the parser the
artwork on its own, which is the input its heuristics were written for.

The page render is still used, unchanged, for the case it was built for: a
scanned form with no text layer at all.

### Alternative B: treat page 3 as the label by page number

Rejected: it is edition-dependent and the author's document is one edition of
many. TTB F 5100.31 (04/2023) states that previous editions are obsolete without
saying what they contained, and nothing establishes that every edition puts the
affixed labels on the same page, or that every filing affixes the same number of
labels. A rule keyed to a page number would work on one file and fail silently
on the next, which is the failure mode A-17's risk paragraph already warns
about. The size floor is a property of what a label scan looks like rather than
of where a particular edition puts it.

### Alternative C: a classifier that decides whether a picture is a label

Rejected as unbuildable at this scope and unnecessary at this one. There is no
labelled corpus of "picture from a COLA filing" to train or validate anything
against, and inventing one would be inventing evidence. What is done instead is
weaker and honest: the largest image that both read and yielded at least one
label value is preferred over a larger one that yielded none, the floor removes
the furniture, and the response says which image was used and what it gave up,
so a wrong pick is visible to the agent rather than silent.

### Alternative D: leave it, and have the agent photograph the label

Rejected: it is what v1.0.1 did, and the author's evidence is what it costs. An
agent holding a filed application that contains the label artwork was being told
to go and find a bottle to photograph, or to type values that were sitting in
the file they had already uploaded.

## Consequences

**Positive**

- The author's own document now reconciles all five compared fields from one
  uploaded file, where v1.0.1 reconciled two.
- Two of the three values A-17 records as "not items on the form" are
  recoverable after all, for filings that embed their artwork. A-17 is amended
  to say so rather than left to imply they are unavailable.
- It is what makes a single upload possible at all: a submission of the
  application alone now has a label side to check, which is what the one-upload
  change that follows this ADR depends on.
- The artwork is flat, so it plays to the pipeline's strength rather than to the
  cylinder problem that is still unsolved (SG-1).

**Negative**

- Reading pictures costs OCR time. A document with four surviving images pays
  about four label reads, on top of parsing. `TTB_MAX_ARTWORK_IMAGES` bounds it
  and the response reports how many were read.
- The size floor is a judgement, not a measurement. A filing that embeds a large
  photograph of something that is not a label can have it read and, if it
  yielded no label value while a smaller real label did, still lose to the real
  one; but a filing whose only large image is not a label will have that image
  offered as the label side. The response says so, and the agent can see it.
- Values from artwork can be misread in ways text-layer values cannot. That is
  why the source is reported per field rather than folded in.

**Risks accepted**

- **The self-consistency risk, which is the serious one.** An agent could read
  a green result on an application-only submission as "this product is
  compliant". It is not that; it is "the artwork on file agrees with the form on
  file". The mitigation is that the response and the interface both say so, in
  the agent's words, on every such result. It is a mitigation that depends on
  the agent reading it, exactly as ADR 0008's confirmation control does.
- **No real filing has been parsed.** Every fixture is generated at test time by
  `samples/formmaker.py`, which now embeds artwork as an image XObject. The
  behaviour is verified against synthetic documents shaped like the author's,
  not against the author's, because a filed application carries an applicant's
  permit number, signature and named person and cannot be committed
  (docs/07_TEST_STRATEGY.md section 8). This bounds the claim and is tracked as
  [OQ-24](../OPEN_QUESTIONS.md#oq-24) alongside the existing
  [OQ-22](../OPEN_QUESTIONS.md#oq-22).
- **PDFium is still not thread-safe.** Image extraction is one more thing done
  under `_PDFIUM_LOCK`; the OCR of what it produced is deliberately done outside
  it, so a batch of documents still spends its expensive step in parallel.

## Effect on the batch path

**A batch row still requires its label image, and the artwork inside a paired
document is not used as the label side there.** ADR 0009 is unchanged by this
ADR, and the reason the two differ is worth stating rather than leaving as an
inconsistency: rows are enumerated from the submitted images, which is what lets
the first line of the stream report a total before any document has been read,
and NFR-2's progress display depends on that total. Enumerating the union of
image stems and document stems instead would be a real simplification for an
importer whose filings carry their own artwork, and it is the obvious next step;
it is not taken this session because it changes what a batch is, and that is
ADR 0009's subject rather than this one's.

What a batch does get from this ADR: where a row has both an image and a
document, the document's artwork now fills application-side values its text
layer left empty, exactly as on the single-label path, and the image the agent
submitted is still the label side.

## References

- The author's evidence, 2026-08-29: a real TTB F 5100.31 filing, three pages,
  with the label artwork embedded on page 3 at 1750 by 1150
- TTB F 5100.31 (04/2023), item 15, transcribed from the form downloaded during
  development from `https://www.ttb.gov/system/files/images/pdfs/forms/f510031.pdf`
- [ADR 0008](0008-cola-form-as-application-input.md), the COLA document as
  application input
- [ADR 0009](0009-batch-cola-documents.md), what a batch is made of
- [ADR 0003](0003-local-ocr-default-bedrock-optional.md), the local OCR pipeline
  this reuses unchanged
- Assumption [A-17](../ASSUMPTIONS.md#a-17), the form field map, amended by this
  ADR
- [FR-11](../03_REQUIREMENTS.md), the label application as the input
- `backend/tests/test_embedded_artwork.py`,
  `frontend/src/__tests__/embeddedArtwork.test.tsx`
