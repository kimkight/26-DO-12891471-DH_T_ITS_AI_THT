# ADR 0009: A batch is label images plus COLA documents, paired by filename stem

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-28 |
| Author | Kimberly D. Kight |
| Decision reference | Rewrites the FR-8 contract; supersedes assumption A-14; extends FR-11 and [ADR 0008](0008-cola-form-as-application-input.md) to the batch path; leaves [ADR 0006](0006-batch-execution-model.md) intact |

## Context

The question this answers was the author's: **why are we assuming the batch is
a CSV? Where would these CSVs even come from?**

The honest answer was already written down in this repository, in assumption
A-14: "No source states this format; it is assumed." Sarah Chen names the volume
and the pain, "we get these big importers who dump 200, 300 label applications
on us at once. Right now we literally have to process them one at a time."
[Source: Sarah Chen interview] She does not say how the application data
arrives, and neither does anyone else.

So where did the CSV come from? From this project, in Session 3. FR-8 needed
some way to attach application data to 300 images, no COLA document parser
existed yet, and a CSV keyed on image filename was the least invented option
available at that moment: `samples/expected.csv` already keyed ground truth on
image filename, and filename was the only identifier present on both sides of a
submission. A-14 recorded all of that, including the risk, and named exactly
what would falsify it: "asking Sarah Chen or Janet what an importer actually
sends today".

**Nothing in the world produces that CSV.** An importer does not send a
spreadsheet of brand names and net contents. What an importer files with TTB is,
per application, a COLA form plus the label images affixed to it. An agent
holding a bulk submission is holding documents and pictures, not a table. To use
the batch path as it stood, an agent would have had to sit down and type 300
rows of the data they were trying not to type, which is the work FR-11 exists to
remove and the work Sarah says takes her team all day.

FR-11 changed what is possible. `app/application_form.py` reads a COLA document
locally: form fields, then the text layer, then OCR, with no network call and no
credential (ADR 0008). The batch path can now take what actually exists.

## Decision

**A batch submission is label images plus COLA documents, paired by filename
stem. The CSV path is removed, not kept alongside.**

### The pairing rule, exactly

The stem is **the filename with its final extension removed, compared without
regard to case**.

- `0001-stones-throw.png` pairs with `0001-stones-throw.pdf`.
- `0001-STONES-THROW.PDF` pairs with `0001-stones-throw.png`: case is folded,
  because an agent's file manager and an agent's scanner disagree about it
  routinely and a pairing that failed on `.PDF` against `.pdf` would be a puzzle
  rather than an error.
- Only the **final** extension is removed, so `0001-stones-throw.front.png` has
  the stem `0001-stones-throw.front` and pairs with
  `0001-stones-throw.front.pdf`, not with `0001-stones-throw.pdf`.
- Any directory part a browser sends with the name is dropped: the pairing is on
  names, not on paths.

The rule is implemented once, as `pairing_stem` in `backend/app/batch.py`, and
mirrored in `frontend/src/lib/pairing.ts` so the interface can state the result
before anything is sent. It is stated on the batch page in the agent's words, on
screen rather than behind a disclosure, because it is what an agent has to do to
their filenames before they can use the page at all.

### On the wire

One multipart request to `POST /api/verify-batch`, carrying repeated `images`
parts and repeated `application_documents` parts. The `applications` CSV part is
gone. The response is unchanged: NDJSON, one line per item, emitted as each
finishes (ADR 0006).

Each document is parsed by the FR-11 parser, inside the worker pool, per row.
That is where the cost is parallelized and where a document that cannot be read
becomes one row's error rather than the batch's. Every value on the batch path
is therefore parsed rather than typed, and each row's result carries the parsed
block and the per-field source, exactly as a single-label submission with a
document attached does.

### What is an error, and whose

FR-8's isolation rule is unchanged: one bad item is that item's error and the
rest of the batch still returns results.

| Case | Reported as |
| --- | --- |
| An image whose stem matches no document | `missing_application_document`, on that image's line |
| A document whose stem matches no image | `unmatched_application_document`, on its own line |
| Two documents on one stem | `duplicate_application_document`, on the image's line |
| Two images on one stem | `duplicate_label_stem`, on each image's line |
| A document that cannot be read | `unreadable_application_document`, on that image's line, naming the document |
| A document of a type not accepted | `unsupported_application_document`, on that image's line |

Two refusals stay at batch level, because there is nothing to attach them to and
repeating one message 300 times down the stream would tell an agent nothing the
first line did not: a submission with no images at all (`empty_batch`) and a
submission with no documents at all (`missing_application_documents`, whose
message states the pairing rule).

The count limit is enforced before anything is processed, on both sides: more
than `TTB_MAX_BATCH_FILES` images, or more than that many documents, is refused
with the limit named (FR-8, NFR-7, A-1). The limit is on labels, and a batch
carries one document per label.

### Beverage type, and what it does not affect

The beverage type for a row comes from that row's document. Where the document
does not state it, the row says so rather than inferring one: a Registry
printout for a bourbon names no product type, and a ticked checkbox cannot be
read out of a text layer (A-17).

**No per-field comparison reads it, and that is worth stating rather than
implying.** A-12's proof cross-check keys off a proof statement the label itself
carries, and A-13's range handling keys off a range in the value; neither
branches on a declared beverage class. So an unstated beverage type costs the
comparison nothing today. It is carried and reported because the interface asks
for it and because A-12 and A-13 name it as the class that would decide which
rule applies if a future rule ever needed deciding. What is not done is guessing
it from the class or type designation.

### One photograph per label, still

ADR 0007's several photographs of one label stay on the single-label path. A
stem pairing several images to one document would need a rule for a group only
partly readable and an answer for what a per-row error means when one photograph
of three failed. None of that is difficult and none of it is asked for by any
source, so it is not invented here. Two images on one stem are an error, not a
multi-photograph label. The limitation is asserted in
`backend/tests/test_multi_photo.py::TestTheBatchPathIsUnaffected` and in
`test_batch.py::TestPairing`, and ADR 0007's own limitation note is updated to
say it against this contract rather than against the CSV one.

## Alternatives considered

**Keep the CSV alongside the documents.** Rejected. It is two input contracts to
build, test, document and explain, and an agent's first question would be which
one to use. The CSV's only origin story was our own assumption: there is no
population of users with CSVs to preserve compatibility for, and no source that
ever asked for one. Keeping a path because it exists, when the thing it was
standing in for now exists properly, is how a prototype accumulates the
complexity it was supposed to avoid.

**One combined PDF carrying all the forms.** Rejected. Pairing becomes
page-guessing: the tool would have to decide where one application ends and the
next begins, and then which label image each page belongs to, with nothing on
either side to key on. Every failure mode of that is a silently wrong pairing,
which is the worst outcome this tool can produce, because a wrong pairing
compares a label against someone else's application and can report a confident
match. Filename stems fail loudly instead.

**Pair by an identifier inside the document**, the TTB ID or the serial number.
Rejected for this session, and it is the strongest of the three. It would
survive renamed files, which stems do not. But it requires reading every
document before anything can be paired, so a batch could not report its total
until every document had been parsed; it depends on the parser finding that
identifier, which is A-17 territory and unverified against a real filing
(OQ-22); and it still needs a fallback for a document where the identifier is
not found. It is recorded in OPEN_QUESTIONS as the thing to ask Sarah Chen and
Janet about, alongside what an importer actually sends.

**Ask the agent to pair the files in the interface.** Rejected. For twelve
labels it is tolerable; at Sarah's 300 it is the manual work the feature exists
to remove.

## Consequences

**What improves.** The batch takes what an importer actually files. The 300 rows
of retyping the CSV silently required are gone, and the batch path gets FR-11's
per-field honesty for free: every row says where its application values came
from, what its document did not carry, and why.

**What an agent has to do instead.** Name their files so each pair matches. That
is a real cost and it is not nothing, but it is a rename rather than a
transcription, it is visible before the batch runs, and a mismatch names the
file it is about.

**What gets bigger, on the defaults, and deliberately not on the deployed
task.** A batch envelope now carries a document per image, so the application's
derived `effective_max_batch_bytes` is twice what it was: 600 files at 10 MB,
about 6 GiB, and FastAPI parses the whole envelope before the route runs.

**The deployed configuration does not follow that.**
`infra/terraform/ecs.tf` pins `TTB_MAX_BATCH_BYTES` at 3 000 MiB, chosen from
the memory budget of an 8 GiB task rather than from the file count, and an 8 GiB
task cannot hold a 6 GiB payload. So on the deployed target the envelope is
unchanged, and the consequence of this ADR there is a refusal rather than more
memory: a batch whose files total more than 3 000 MiB is rejected from its
Content-Length before the body is read, with the limit named. That is the safe
failure. In the ordinary case it costs nothing, because the document is the
small half of each pair, kilobytes of Registry printout beside megabytes of
photograph. The reasoning is written out in
[09_DEPLOYMENT.md](../09_DEPLOYMENT.md) section 4.4, and the figure that would
justify raising it is the section 9 CloudWatch `MemoryUtilization` measurement
(OQ-13 item 6).

**A concurrency bug this change surfaced.** PDFium is not thread-safe, and the
batch path reads documents in a worker pool. Reading two at once segfaults the
process, which takes the stream and every completed result with it: a
whole-batch failure NFR-2 forbids and one no per-row error can catch, because
the process is gone. Every call into PDFium is now made under one lock in
`app/application_form.py`, with the OCR fallback deliberately left outside it so
a batch of scanned documents still spends its expensive step in parallel. This
is the same shape of problem as the OpenMP one in `app/ocr.py`, found the same
way: a library that is fine on the single-label path and not fine in a pool.

**What slows down.** Each row now parses a document as well as reading a label.
For a digitally generated PDF that is milliseconds. For a scanned document it is
another OCR pass, so a batch of scans costs roughly twice a batch of
text-layer PDFs. No source states a batch latency target (OQ-6), and the figure
belongs in the section 9 measurement.

**What is not verified.** The same limit ADR 0008 records: no real filed
application and no real Registry printout has been parsed, so a batch of real
documents has never been run (OQ-22). Every parsed value is still reported for
what it is, and a value the document did not carry is not compared rather than
guessed, so the failure mode is a field an agent has to check by hand rather
than a wrong comparison.

**What is deleted.** `parse_applications_csv`, the column contract, and the
CSV's per-row reconciliation errors. A-14 is marked superseded in
[ASSUMPTIONS.md](../ASSUMPTIONS.md) rather than removed, because the history of
why the CSV existed is the reason this ADR is short.

## Amendment, 2026-08-29: does a batch document that carries its own artwork still need a paired image?

**Yes. A batch row still requires its label image, and this ADR is otherwise
unchanged.**

[ADR 0010](0010-embedded-label-artwork.md) reads the label artwork embedded in a
COLA document and, on the single-label path, uses it as the label side when the
agent uploaded no photograph. The obvious question is whether that makes the
paired image optional here too. It does not, this session, and the reason is
this ADR's own design rather than an oversight:

**Rows are enumerated from the submitted images.** That is what lets the first
line of the stream report a total before any document has been read, which is
what NFR-2's progress display depends on: "batch progress is observable to the
user rather than presenting as a frozen page". Enumerating the union of image
stems and document stems instead would still let the total be known first, but
it would also mean a batch of 300 documents and no images pays a full artwork
OCR read per row before anything can be said about any of them. That is a
different contract for what a batch is, and it is this ADR's subject rather than
ADR 0010's.

**What a batch does get from ADR 0010.** Where a row has both an image and a
document, the document's embedded artwork now fills application-side values its
text layer left empty, exactly as on the single-label path, and the source is
reported per field. So a batch of filings whose class or type, alcohol content
and net contents appear only on the affixed labels now reconciles those values
where it previously reported them as not found. The image the agent submitted is
still the label side, which is right: a photograph of the product is evidence
about the product, and the artwork on file is not.

**This is a real simplification left on the table, and it is named as such**, so
the author knows about it. An importer whose filings carry their own artwork
could submit documents alone and skip half the files. It is the obvious next
step for this path, it changes what a batch is, and it should be decided here
rather than inherited from a change made for the single-label view.

## Amendment, 2026-09-02: superseded on the pairing contract by ADR 0020

**The question the previous amendment left on the table is decided, the other
way, in [ADR 0020](0020-batch-items-are-derived.md).** A batch is one pile of
files in one `files` part; a row is every file that shares a stem; each row is
classified and run through the single-label check; and a filed application
that carries its own artwork is a complete row on its own. The two required
parts, the "image with no document" and "document with no image" errors, and
the refusal of a batch with no images are gone.

**What this ADR still decides.** The stem rule, exactly as written above, is
what groups files into rows, and one row holds one label image. The reasoning
for taking documents rather than a CSV, and the alternatives rejected, stand.
The assumption the previous amendment rested on, that rows had to be
enumerated from the images for the total to be known first, was wrong: rows
are enumerated from names, which is cheaper and needs no image. ADR 0020
records the assumption and why it is gone.
