# ADR 0011: One upload, sorted by the server

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-29 |
| Author | Kimberly D. Kight |
| Decision reference | Adds FR-12; depends on [ADR 0010](0010-embedded-label-artwork.md) for the label side of an application-only submission; keeps [ADR 0007](0007-multi-photo-single-label.md) and [ADR 0008](0008-cola-form-as-application-input.md) intact underneath; leaves [ADR 0009](0009-batch-cola-documents.md) alone |

## Context

The author used the deployed v1.0.1 build on 2026-08-29 with a real COLA
document and could not submit it, because a label image was also required. Their
words: **"if COLA is uploaded, I don't also need an image."** And the
instruction that followed: **"these should be combined; just one upload;
simplify the interface. You should be able to upload (pdfs or images)."**

The interface asked for two different things in two different places, because
the two features arrived separately. ADR 0007 added photograph slots for one
label; ADR 0008 added a second picker for the application. Each was right on its
own, and together they produced a screen that asks an agent to classify their
own files before the tool has looked at any of them.

**That question is one the agent should not have to answer, and the server can.**
A file arriving in the photo picker was read as label artwork whatever it was,
so an agent who dropped their COLA PDF there got a form read as a label. The box
is a guess about intent. The file is the fact.

The hard gate mattered too. Before ADR 0010 there was nothing to check an
application against without a photograph, so requiring one was honest. ADR 0010
removed that: a filed application carries the label artwork inside it, so a
submission of the application alone has a label side. The gate had become a
statement about the interface rather than about what the tool could do.

## Decision

**One repeated `files` part on `POST /api/verify`, taking PDFs and images in any
mix, with the server deciding what each file is from the file itself and
reporting that per file.** One file picker in the interface, with the check
enabled as soon as anything is uploaded.

### The classification rule, in full

1. A file whose bytes begin with `%PDF`, or which declares `application/pdf`, is
   the **application side**. The bytes are checked first, because a browser
   labels a file from its extension and an agent can rename it. Nothing is
   decoded and no OCR runs to reach this answer.
2. An image is read once through the ordinary OCR pipeline, and what comes back
   decides it. If the text carries a COLA form or Public COLA Registry marker,
   or the application parser finds at least one mapped caption value in it, it
   is the **application side**. Otherwise it is a **label side**.
3. An image that cannot be decoded at all is a **label side**, carrying its
   error. FR-9's message for an unreadable photograph tells an agent to send a
   better one, which is what they need to hear; routing an undecodable file to
   the application parser would produce a message about a document instead.

The markers in rule 2 are printed strings from the documents themselves, not
inferences about them: the form number `TTB F 5100.31`, its OMB control number
`1513-0020`, the application's own title, the bureau's name, and a Registry
detail page naming itself. They are matched loosely because this runs over OCR
output, where a space or a full stop routinely goes missing. The weaker half,
finding a mapped caption value, is there because a photograph of a form may be
cropped past the letterhead; a label carries no `BRAND NAME:` caption, because a
label prints the brand rather than captioning it.

**Each image is read exactly once.** The OCR result produced while classifying
is handed to whichever side the file lands on, so classifying costs nothing
beyond the read that side was going to pay for anyway. Measured on a session
runner: single-label verification stayed at about 1.5 seconds end to end, which
is where it was before this change.

### The API contract, and why this shape

`POST /api/verify` takes one repeated `files` part. `image` and
`application_document` remain accepted, and whatever arrives in either goes
through the same classifier, so a caller written against v1.0 keeps working and
a COLA PDF sent in the `image` part is still read as the application. The
OpenAPI description says exactly that on both.

`POST /api/classify` is added for the interface, in the same sense
`POST /api/read-application` was added by ADR 0008 and for the same reason: the
agent has to be told what each file was taken to be, and has to see the
application values before a check runs, so they can confirm or correct them
(FR-3). A caller with no interface should send everything to `POST /api/verify`
in one request instead, which classifies the same way and reads each image once.

**The batch path keeps its two named parts, `images` and `application_documents`,
unchanged.** The two paths differ, and the reason is worth stating rather than
leaving as an inconsistency: ADR 0009 pairs a batch by filename stem, and the
agent submitting 300 labels has already sorted them into two piles to name them.
The single-label agent has one pile. Folding the batch into one part would mean
classifying 600 files before the stream could report a total, and NFR-2's
progress display depends on that total being known first. It is recorded here so
that the next person changing either one knows the other exists.

> **Superseded on this point by [ADR 0020](0020-batch-items-are-derived.md),
> 2026-09-02.** The batch path takes the same one `files` part. The total is
> still known first, because rows are grouped by name before anything is read
> and classified inside the pool, per row; the assumption above, that the
> total could only be known by knowing which files were images, was the thing
> that kept the two paths apart, and it was wrong. The two older part names
> still work, exactly as `image` and `application_document` do here.

### What is refused, and how

| Case | Response |
| --- | --- |
| Nothing uploaded at all | 422 `no_files`, naming what to upload |
| More label pictures than `TTB_MAX_LABEL_PHOTOS` | 413 `too_many_photos`, naming the limit |
| More than one file classified as the application | 413 `too_many_application_documents` |
| A file whose type is on neither list | 415 `unsupported_application_document`, naming the accepted set |
| An application with no readable artwork, and no photograph | 422 `no_label_to_check`, naming the missing piece and offering the photo upload |

The last one is FR-9's shape rather than a validation error on a form field:
nothing the agent typed is wrong, and the response carries no field outcomes at
all.

### The three valid submissions

All three complete, and all three are tested end to end:

1. **The application document only.** ADR 0010's embedded artwork is the label
   side, and the result says so.
2. **A label photograph plus typed values.** Unchanged from v1.0.
3. **Both.** The photograph is the label side, because a picture of the bottle
   in front of the agent is evidence about that bottle and the artwork on file
   is not.

## Alternatives considered

### Alternative A: keep two pickers and route server-side anyway

Rejected. It would fix the misclassification without fixing what the author
asked about. The instruction was "just one upload; simplify the interface", and
two controls that both accept everything are harder to explain than one, not
easier: an agent would still be asked to choose, and the choice would now mean
nothing.

### Alternative B: classify in the browser, by file type

Rejected, and it is the tempting one because it costs nothing. A browser knows
only the extension and the declared MIME type, both of which are what an agent
renames. A photograph of a printed COLA form is `image/jpeg` and is the
application side; a PDF of a label proof is `application/pdf` and might not be.
Deciding in the browser would put the classification exactly where the least
evidence is, and would mean the interface asserting something it has not read.

### Alternative C: one call that classifies and checks, with no `/api/classify`

Rejected for the interface, kept for the API. The parsed application values have
to reach the agent as editable fields **before** the comparison runs, which is
ADR 0008's control and FR-3's philosophy: the tool reads, the agent judges.
Folding it into one call would either skip that confirmation or run the check
twice. An API caller with no confirmation step does get exactly this: one
`POST /api/verify` with everything in `files`.

The cost is recorded rather than hidden: a label picture is read once by
`/api/classify` when the agent chooses it, and once again by `/api/verify` when
they press the button. The agent's wait for the check is unchanged, because the
first read happens while they are still working; what it costs is server CPU.

## Consequences

**Positive**

- The author's case works: upload the COLA document, press the button.
- A misfiled file is read correctly instead of being read as the wrong thing.
- One labelled control instead of two pickers plus a row of numbered slots and
  an "add another photo" button. That is three fewer stops on the keyboard walk.
- Every file's classification is reported and shown, so a wrong call is visible.

**Negative**

- A label picture is read twice on the interface path, once to classify and once
  to check. Alternative C records why, and an API caller pays it once.
- The classification can be wrong. A photograph of a label that happens to
  contain the words "Alcohol and Tobacco Tax and Trade Bureau", which some
  labels do print, would be taken for a form. It is reported per file, and the
  agent can remove it and try again; there is no silent path.
- `ApplicationUpload.tsx` is removed and its tests are rewritten. The assertions
  about what a parsed application does to the form are unchanged; what changed is
  the control the file goes into.

**Risks accepted**

- **A label that names the bureau.** The marker list is the strongest evidence
  available without a classifier nobody can validate (ADR 0010, alternative C,
  records the same reasoning). The mitigation is visibility, not certainty.
- **The two paths differ.** Single-label sorts one part; batch keeps two. Stated
  above so that it is a decision rather than a drift.

## References

- The author's evidence and instruction, 2026-08-29, from using the deployed
  v1.0.1 build
- [ADR 0007](0007-multi-photo-single-label.md), several photographs of one label
- [ADR 0008](0008-cola-form-as-application-input.md), the COLA document as
  application input
- [ADR 0009](0009-batch-cola-documents.md), what a batch is made of
- [ADR 0010](0010-embedded-label-artwork.md), the label artwork inside the
  application, which supplies the label side this depends on
- [FR-12](../03_REQUIREMENTS.md), one upload
- `backend/app/classify.py`, `backend/tests/test_one_upload.py`,
  `frontend/src/components/UploadPanel.tsx`,
  `frontend/src/__tests__/oneUpload.test.tsx`
