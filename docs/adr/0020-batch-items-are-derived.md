# ADR 0020: A batch row is derived from its files, and a filed application is a row on its own

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-02 |
| Author | Kimberly D. Kight |
| Decision reference | Rewrites the FR-8 contract and US-9; supersedes the two-part contract and the "pairing is a precondition" half of [ADR 0009](0009-batch-cola-documents.md), whose stem rule it keeps; extends [ADR 0010](0010-embedded-label-artwork.md) and [ADR 0011](0011-one-upload.md) to the batch path, which ADR 0011 had explicitly declined to do; leaves [ADR 0006](0006-batch-execution-model.md) intact |

## Context

The author, having tested the deployed v1.2.1 batch page:

> "I had not been focusing on the bulk upload. I just tested and it is missing
> features we discussed. I need for the functionality of that page to mimic
> the check on label page. It should also accept the COLA application, pdf or
> images (with a single choose file; not 2). The results should be to the right
> but in table format in a list."

**What the page did.** Two file inputs, "Label images" and "COLA documents",
paired by filename stem (ADR 0009). The check stayed off until both were
chosen: "Choose the label images and their COLA documents to turn on the
check." An image with no document of the same name was an error line
(`missing_application_document`), a document with no image was an error line
(`unmatched_application_document`), and a batch of documents alone was refused
before it started (`missing_application_documents`).

**What the single-label page did by then.** Since v1.1.0 it takes one pile of
files and the server decides what each is (ADR 0011); since ADR 0010 a filed
application that carries its own label artwork is a complete submission,
checked against that artwork; since v1.3.0 a photograph alone is a valid
submission, checked for what a label must carry (code review finding 19). None
of that had reached the batch page.

**Why not.** ADR 0009's amendment of 2026-08-29 says so exactly: rows were
enumerated from the submitted images, because that let the first line of the
stream report a total before any document had been read, which is what NFR-2's
progress display depends on; and ADR 0011 declined to fold the batch into one
part because "classifying 600 files before the stream could report a total"
would have cost that same property. Both were honest reasons, and both rested
on one assumption: **that the only way to know how many rows a batch has is to
know which files are images.** That assumption is what this ADR removes.

**The three gaps that followed, measured on the running prototype.** It
required an image when a filed COLA application is sufficient on its own; it
asked the agent to think about file roles and to name files to match, when
`/api/classify` already works out what each file is; and its results were not
the results from the other tab, with a vocabulary, a shape and no field-by-field
view of their own. An agent with forty filed applications had to render forty
images out of them, name eighty files in pairs, and then read a different
kind of result.

## Decision

**A batch is one pile of files in one repeated `files` part, the part the
single-label check takes. A row is every file that shares a filename stem.
Each row is classified from its files and run through the single-label check,
so a filed application that carries its own artwork is a complete row on its
own, a photograph on its own is a valid row, and an application and an image
that share a stem are the ordinary pair. Nothing is silently dropped: a file
that cannot be classified, cannot be read, or has no partner is a visible row
with a plain outcome.**

### Classification first

`app/classify.py` decides what each file is from the file (ADR 0011): a PDF by
its header, an image by whether its text reads as a COLA form. On the batch
path this runs per row, inside the worker pool, and the read it produces is
handed on to the check so each image is read exactly once (ADR 0017). The
extension plays no part in which side a file lands on. A scan of the form saved
as `0007.png` and a photograph of the label saved as `0007.jpeg` are the
ordinary pair, which under the two-part contract was an agent's guess and
under an extension rule would have been two images.

### The stem rule is kept, as a convenience

The stem is the filename with its final extension removed, compared without
regard to case, exactly as ADR 0009 defined it and with the plain lower-case
mapping v1.3.0 settled on both sides (finding 21). It is what groups files into
rows, so an agent who names an image to match an application gets them checked
together, and it is the only thing the agent still has to know about naming.
It is documented on the Help tab, not printed on the check screen.

What it no longer is, is a precondition. There is no unmatched document, no
missing document and no batch refused for having no images. The one rule left
is inherited from ADR 0009 rather than added here: **a row holds one label
image.** Two label images on one stem are one ambiguous row, reported as
`duplicate_label_stem` with a message that sends a label with several
photographs to the single-label tab, which reads up to `TTB_MAX_LABEL_PHOTOS`
and merges them (ADR 0007). Two applications on one stem are
`duplicate_application_document`, likewise one row.

### The total is still known first

Grouping is on names alone. The route counts stems before reading a byte, so
the count limit is refused before anything is processed (FR-8, NFR-7), the
stream's first line carries the total (NFR-2), and the page, which groups by
the same rule in `frontend/src/lib/pairing.ts`, lays out one pending row per
label before the batch is sent and fills each in by `position` as its line
arrives. That is the property ADR 0009 and ADR 0011 were protecting, kept
without the assumption they paid for it with.

### The limit is on labels

`TTB_MAX_BATCH_FILES` bounds rows, not files: 300 applications with their 300
images is 300 labels and is accepted (A-1). The envelope limit in bytes is
unchanged and is the bound on the files themselves.

### One check, one module

The body of `POST /api/verify` moved out of `api.py` into `app/check.py`, and
the batch row calls it. That is the mechanism by which the bulk page cannot
fall a generation behind again: a rule added to the single-label check is a
rule on every batch row, because there is no second check to forget. The
interface follows the same shape. The batch tab classifies each file on arrival
with the same call the single-label tab makes and shows the same chip; its
results table uses the same outcome vocabulary and the same `OutcomeBadge`;
selecting a row renders `ResultDetail`, the block lifted out of the
single-label tab, with the same five cards.

### The results table

One table on the right, one row per label in the order submitted, columns
Label, Brand, Class or type, Outcome and Checks. Label is the file name, the
label image's where the row has one. Outcome is the row's worst field, as
before. Checks is the same count the summary line prints, "5 of 5", from one
function so the two cannot disagree. Selecting a row opens the detail under
the table through a `<button>` with `aria-expanded` over the detail region; the
open row carries `aria-current`; focus never moves. Below the layout's
breakpoint, which is the single-label tab's, the two columns stack with the
upload first.

**Sorting is dropped.** The v1.3.0 table sorted by label, result and two
counts because arrival order was no order an agent chose. Submission order is
one, and rows filling in place is what a sort would fight while the stream is
open. The seven-bucket tally above the table is how an agent finds the rows
that need them; a sort is a follow-up if that proves insufficient at 300 rows.

### The older part names still work

`images` and `application_documents` are accepted and folded into the one
pile, exactly as `image` and `application_document` are on the single route
(ADR 0011). A caller written against ADR 0009 keeps working, and a PDF sent as
an image is still read as an application, because the classifier decides.

## Alternatives considered

**Keep two inputs and make the second optional.** Rejected. It keeps the agent
sorting files the server sorts better, keeps the pairing rule on the screen,
and keeps two result vocabularies. The author's words were "a single choose
file; not 2".

**One input, classify everything before the stream starts, then group by
classification.** Rejected, for the reason ADR 0011 gave: 300 images would be
read before the first line could say "1 of 300", which is the frozen page
NFR-2 forbids. Grouping by name first and classifying per row keeps the total
first and the classification inside the pool.

**Derive rows from classification on the page and send explicit rows.**
Rejected. It would make the page's classification calls a precondition of the
check rather than a preview, would need a second request shape, and would let
the page and the server disagree about what a row is. The server groups by the
rule the page previews; the page is never the authority.

**Allow several label images per row now that the check merges photographs.**
Deferred, deliberately. `check_sorted` would accept them tomorrow; what is
missing is a rule for a row whose three photographs read one, two or none, and
what one line's error means then. No source asks for it and ADR 0009's
limitation stands, with a message that names the tab that does merge them.

**Keep the sortable table and add the detail to it.** Rejected for this
release, as above: a sort competes with rows filling in place, and every sort
control is a keyboard and announcement obligation (NFR-5) for a need the tally
already meets. Recorded so it is a decision rather than an omission.

## Consequences

**Positive.** An agent who drops forty filed applications gets forty checked
labels, with no images rendered and no files renamed. What each file was taken
to be is visible before the check, in the same words as the other tab. The
five checks, the five outcome words, the "5 of 5 checks passed" line and the
field-by-field cards are literally the same code on both tabs. A batch of
photographs alone is not an error. The count limit bounds labels, so the
300-label scenario with paired images is accepted as 300 rather than refused
as 600.

**Negative.** A row that used to be "image with no document" now runs the
single-label check on the photograph alone, which is a full OCR pass that
produces two presence checks and three not-compared rows; an agent who meant
to pair it and misnamed the document gets a result rather than an error
telling them so. The grouping sentence above the check counts images on their
own for exactly this reason. Two label images that share a stem are still an
ambiguous row rather than a merged label, and the message has to send the
agent elsewhere. The classification on arrival is one request per file, two
in flight at a time; for images it is an OCR pass each, and the section 9
measurement says what a twenty-file drop costs.

**Risks accepted.** The page's grouping and the server's are two
implementations of one rule; they are asserted on the same vectors on both
sides, and a line whose position the page did not predict is appended rather
than dropped. The old two-part callers are kept working by folding rather than
by a compatibility branch, so they get the new semantics, including that a
document with no image is no longer an error.

**What is deleted.** `SubmittedImage`, `SubmittedDocument`, `DocumentTable`,
`collect_documents`, `plan` and the per-row pairing errors in `app/batch.py`;
the codes `missing_application_document`, `unmatched_application_document` and
`missing_application_documents`; the second `DropZone`, the pairing rule
paragraph and the "Which files are unmatched" disclosure on the batch tab; the
sort controls on the table. ADR 0009 is amended rather than rewritten, because
the history of why the batch took documents at all is the reason this ADR is
short.

## References

- FR-8, FR-11, FR-12 in [03_REQUIREMENTS.md](../03_REQUIREMENTS.md)
- US-9 through US-12 in [04_USER_STORIES.md](../04_USER_STORIES.md)
- Section 4 of [05_ARCHITECTURE.md](../05_ARCHITECTURE.md)
- `backend/app/check.py`, `backend/app/batch.py`, `backend/tests/test_batch.py`
- `frontend/src/components/BatchTab.tsx`, `BatchTable.tsx`, `ResultDetail.tsx`,
  `frontend/src/lib/pairing.ts`, `frontend/src/__tests__/batchTable.test.tsx`
- The measurement of the batch path on self-contained applications in
  section 9 of [09_DEPLOYMENT.md](../09_DEPLOYMENT.md)
