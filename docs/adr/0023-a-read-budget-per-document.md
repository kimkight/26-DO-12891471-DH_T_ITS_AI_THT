# ADR 0023: One document's reading has a ceiling, counted in Tesseract reads, and what it leaves unread is said

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-08 |
| Author | Kimberly D. Kight |
| Decision reference | NFR-1; bounds [ADR 0010](0010-embedded-label-artwork.md) as amended and the OCR fallback of [ADR 0008](0008-cola-form-as-application-input.md); keeps [ADR 0017](0017-read-the-artwork-once.md)'s refusal of a cache |

## Context

NFR-1 says single-label verification returns in about five seconds. Measured
by the author through the browser against the deployed v1.5.0 build, three
real filed COLAs, with the clock started when the file is picked:

| Document | `/api/classify` | `/api/verify` | panels read | reads | result |
| --- | --- | --- | --- | --- | --- |
| mezcal, `samples/real/22118001000389` | 305 to 470 ms | 4816 ms | 1 | 4 | 5 of 5 |
| bourbon, `samples/real/15309001000084` | 414 to 694 ms | 8064 ms | 5 | 19 | 2 of 5 |
| a third filing, no text layer, not committed | 10322 ms | not reached | 0 | | brand and class wrong |

The bourbon's response says where its eight seconds went: `artwork_ocr_ms`
7679 of `elapsed_ms` 7938, `ocr_passes` 5, `tesseract_reads` 19. Nineteen
reads over five panels. The v1.4.0 build read one panel of this document and
returned one of five; #140 and #141 read all five and returned two of five,
with the brand name right, at five times the OCR. That trade bought real
accuracy and its cost was not measured before this session.

**The stopping rule of #141 cannot contain it.** It stops when the panels
read so far carry all five values, and on the bourbon the alcohol content and
the net contents are never found (OQ-39), so it never fires. The document
that fails the checks is the document that does the most work, and the only
thing bounding that work was `TTB_MAX_ARTWORK_IMAGES`, a count of pictures.
A count of pictures bounds nothing about what each picture costs: one
picture is one to eight engine invocations, and the bourbon's five ran 3, 3,
4, 4 and 5.

**The reads cannot be cut without changing the answer.** The obvious lever,
not running the second arm on a panel whose first arm read confidently, is
already the rule: `PREPROCESS_SHORT_CIRCUIT_CONFIDENCE` in `app/ocr.py`,
set at 85 from the 2026-08-29 measurement. Per panel on the bourbon, measured
2026-09-08 on a session container:

| panel | source | first arm | second arm | winner |
| --- | --- | --- | --- | --- |
| 1950 x 862 | colour | colour 0.0, no words | preprocessed 0.0, plain 0.0 | none read |
| 1350 x 300 | monochrome | preprocessed 44.7 | plain 89.9 | plain |
| 1103 x 340 | colour | colour 41.2 | preprocessed 29.0, plain 36.6 | colour |
| 1050 x 309 | monochrome | preprocessed 56.3 | plain 86.8 | plain |
| 187 x 1697 | monochrome | preprocessed 67.0 | plain 23.6 | preprocessed |

No first arm reaches 85, so the short circuit fires on no panel; the two
panels that read well read well on the second arm, which is where the brand
match and the government warning text come from. The mezcal's one panel
reads 89.6 on its first arm and costs one. So on both committed filings the
existing rule already does what it can, and the reads are 19 and 4 before
and after this decision. What is left is to bound the document that carries
more than the bourbon.

## Decision

**One document's reading, its rendered pages and its embedded pictures
together, may cost at most `TTB_MAX_DOCUMENT_READS` Tesseract invocations,
default 24.** The budget is consulted before each picture and before each
page, never inside one: a picture is read whole or not at all, so the last
picture read can carry the count past the line by at most its own reads,
eight at the very most.

**What the budget stops is said, three ways.** Each picture it did not get
to is listed in `artwork_images_accepted` with the status `not_reached`, a
new value kept apart from `not_read` and `not_needed` because it means a
different thing: the values may be on it and nobody looked. Pages it did not
get to are counted in `pages_not_reached`. And a sentence in `notes` says
how many of each were left and at what count, in the voice of the artwork
table's own "not read" copy, so that the batch line and the upload card
carry it in words. `tesseract_reads`, `read_budget` and
`read_budget_reached` on the document block let a caller see the arithmetic.
A budget that truncated silently would be worse than the slowness, because
"not found" would then mean "not looked for".

**Twenty-four** is the picture ceiling, eight, times the least a picture
costs when its first arm does not settle it: the orientation call, the
preprocessed arm and the plain arm. It admits both committed filings in
full, the bourbon's 19 with one worst-case panel of margin, so it changes
no outcome on any measured document. It cuts the runaway case from 40 reads,
eight pictures at the bourbon's worst per-panel cost, to 24. At the
bourbon's measured 404 ms per read that is about ten seconds of OCR, which
is over NFR-1, and this is stated rather than smoothed: **the ceiling does
not make the bourbon meet the target. It stops a document that carries more
than the bourbon from running away.** The bourbon's own shortfall is
reported in the traceability matrix as the requirement's acceptance criteria
demand.

## Alternatives considered

### Alternative A: a budget in milliseconds

A wall-clock ceiling on the reading, say five seconds of OCR per document,
checked between pictures the same way. It would make NFR-1 true by
construction, on every host, for every document, which is its whole
attraction, and it was the closer call of the two.

Not chosen, for one reason with three faces. The answer would depend on the
host. The same filing would be read in full on a fast task and cut short on a
slow one; on the same task it would be read differently while a batch is
saturating the one vCPU the task has (section 9 measured that CPU at 99.8
percent during OCR); and no test could pin which pictures get read, so the
behaviour could only be asserted through stubs. A compliance tool that gives
one agent five of five and their colleague three of five and two
`not_reached` on the same document, because of what else the server was
doing, has made its answer a function of load. Reads give the same document
the same answer everywhere.

What is given up is stated: a read costs between 117 ms (the 187 by 1697
strip) and 1485 ms (the 1750 by 1150 sheet at full resolution) on the same
container, so a ceiling in reads bounds the clock only within that ratio.
**What would change the choice:** a measured need for a hard wall-clock
bound per request, for example an upstream timeout shorter than the worst
case 24 reads can cost on the deployed hardware. Then the right shape is a
milliseconds ceiling *on top of* this one, with the same `not_reached`
reporting, and the host-dependence accepted and documented.

### Alternative B: lower `TTB_MAX_ARTWORK_IMAGES` instead

The count already exists and is already reported. But it is the count that
was four and left the bourbon's fifth panel unread (#141), and lowering it
puts it back in the position of deciding correctness on a real filing. A
picture count cannot see that five panels cost 19 reads on one document and
would cost 10 on another.

### Alternative C: read fewer arms per panel

Skip the plain arm once the preprocessed arm reads confidently, or skip the
transforms once the colour arm does. Both are already the rule, measured and
set in v1.0.1 and v1.1.0, and the table above shows they fire on neither of
the bourbon's panels that matter. Cutting a second arm on that filing would
remove the reads that produced the brand match. Reordering the arms, plain
before preprocessed on a monochrome panel, would save two reads on the
bourbon and is a reversal of a measured v1.0.1 decision on the twelve-label
set that this session did not re-measure; it is recorded here as the next
candidate, not done.

### Alternative D: a cache of reads across the two requests

Refused in ADR 0017 and refused again. NFR-6 is printed on every screen.

## Consequences

**Positive.** No single document can run away: the worst case is bounded at
24 reads plus one picture, whatever the filing carries. Every read the
budget stops is visible in the response and on the screen, so a reviewer can
tell an unread panel from an empty one. The counts are exact and asserted in
`backend/tests/test_read_budget.py`.

**Negative.** The bound is loose in time, by the ratio of the cheapest read
to the dearest. The bourbon still costs 19 reads and about eight seconds on
the deployed build; the budget does not fix that and does not claim to.

**Risks accepted.** A filing that embeds more than eight pictures above the
floor, or a scan whose pages and pictures together cost more than 24 reads,
comes back with values reported not found and the reason stated. An operator
who would rather read everything raises `TTB_MAX_DOCUMENT_READS`; one on
slower hardware lowers it, and the response says what was cut either way.

## References

- NFR-1 in [03_REQUIREMENTS.md](../03_REQUIREMENTS.md)
- [09_DEPLOYMENT.md](../09_DEPLOYMENT.md) section 9, the deployed-build gate
- `backend/app/config.py`, `max_document_reads`
- `backend/app/application_form.py`, `_ReadBudget`
- OQ-39 in [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md), why the bourbon's values are not found
