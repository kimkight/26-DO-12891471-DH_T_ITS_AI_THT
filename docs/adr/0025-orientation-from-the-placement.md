# ADR 0025: A picture lifted out of a PDF is turned the way the page places it, and Tesseract is asked only when that reading is sideways type and nothing else

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-08 |
| Author | Kimberly D. Kight |
| Decision reference | NFR-1, FR-1; narrows [ADR 0003](0003-local-ocr-default-bedrock-optional.md)'s orientation call to the input it was measured on; amends the ceiling arithmetic of [ADR 0023](0023-a-read-budget-per-document.md); extends [ADR 0010](0010-embedded-label-artwork.md) |

## Context

The bourbon filing in `samples/real/` cost 19 Tesseract reads on the
session container that measured it for ADR 0023, and 7 of the 19 were
orientation: one orientation and script detection (OSD) call per panel, and
the two reads of the 180-degree second opinion on the one panel where OSD
answered under the floor. The mezcal beside it cost 4, of which 3 were the
same: one OSD call and the second opinion. About 1.4 seconds of the
bourbon's 6.7 and 0.9 of the mezcal's 3.7, on that container.

**What the orientation call bought on the two filings, panel by panel.**
Measured 2026-09-08, Tesseract 5.3.4, on the working grayscale exactly as
`preprocess` asks it:

| panel | OSD verdict | confidence | second opinion | turn applied | reads spent |
| --- | --- | --- | --- | --- | --- |
| mezcal, 1750 x 1150 | 180 | 0.03 | 0 at 62.2 beats 180 at 23.3 | 0 | 3 |
| bourbon, 1950 x 862 | unable to answer | | | 0 | 1 |
| bourbon, 1350 x 300 | 0 | 2.06 | | 0 | 1 |
| bourbon, 1103 x 340 | unable to answer | | | 0 | 1 |
| bourbon, 1050 x 309 | 180 | 0.15 | 0 at 87.1 beats 180 at 22.9 | 0 | 3 |
| bourbon, 187 x 1697 | unable to answer | | | 0 | 1 |

The turn applied is 0 on every panel. OSD was right above the floor on one
panel, wrong on two, and both times the second opinion of ADR 0003 caught
it, and unable to answer on three. Ten reads for no turn.

**Whether any panel is stored rotated was established before deciding
anything, three ways, and the answer is no.** First, from the file: every
one of the eight pictures on the two filings is drawn with an axis-aligned,
positive-scale placement matrix (the form `[a 0 0 d e f]` with `a` and `d`
positive) on a page whose `/Rotate` is 0, which is the document itself
saying each picture appears the way its raster is stored. Second, by
reading: the three panels that read well read well at 0 degrees and badly
at 180 (the mezcal 89.6 against 33.3 on the colour arm, the 1350 by 300
panel 89.9 against 26.2 and the 1050 by 309 panel 86.8 against 27.0 on the
plain arm), and the panels that read badly read badly at every rotation.
Third, by eye, since the filings are public and committed: every panel is
upright, and the two OSD verdicts of 180 were wrong.

**The strip.** The session that asked for this work took the 187 by 1697
strip to carry the bourbon's alcohol content and net contents, because the
synthetic fixture in `tests/test_artwork_panels.py` puts them there, and it
does not. The strip carries two script signatures set along its length, a
logo and a placeholder serial number, and none of the five values. It is
stored upright: the serial number reads upright at 0 degrees and OSD, given
sideways handwriting and nothing else, cannot answer. Its 67.0 preprocessed
is one word, a lone glyph. The three values it was thought to carry are on
the bottom line of the 1950 by 862 painting, as OQ-39 has said since
2026-09-06 and as the panel shows, and no arm finds them there on this
Tesseract; that is OQ-39's own problem, text-region detection, and it is
not this decision's. `samples/real/README.md` said the label carries no net
contents statement; the painting's line ends in one, and the README is
corrected.

**The weaker argument for an embedded raster, taken seriously.** The page
path already runs with orientation off, on the grounds that a rendered page
is the right way up. An embedded picture is stored in its own coordinate
space, and the page can place it turned, so the bytes can be sideways while
the page looks upright. That is true, and it is also exactly what the file
states: the placement matrix and the page rotation are in the PDF, exact,
and free. What the file does not state is which way the *type* on the
picture runs. A side strip printed to be read along its length, affixed to
the form the way it is, is placed upright and reads sideways, and OSD is
what turned it. The five-panel fixture has one, set vertically, and at the
placement turn it reads as 48 words, every one of them sideways by the
pipeline's own `OcrLine.sideways` test and none upright. No real panel
reads like that; the nearest is the 1103 by 340 panel, whose arced
lettering reads as five tall boxes beside three upright words.

## Decision

**A picture lifted out of a PDF is turned by the quarter-turn the document
applies to it, reported as `placement`, and no orientation call is made.**
`_placement_rotation` reads the clockwise turn off the picture's placement
matrix composed with the page's `/Rotate`, requiring both columns of the
matrix to agree on a quarter-turn and the determinant to be positive, so a
slant, a skew or a mirror is not read as a turn; `extract_text` takes it as
`placement_rotation`, applies it, and reports the method with no confidence
and no check, because it is a fact about the file and not a verdict. The
composition is not argued from sign conventions: `tests/test_placement_orientation.py`
renders every quarter-turn placement under every page rotation with PDFium
and checks that the raster, turned by the figure, is the picture the page
shows.

**Where the reading taken at the placement turn shows sideways type and
nothing upright, Tesseract is asked after all.** `_reads_as_sideways` is
the gate: no upright word at all, and at least one sideways line of two or
more words. It costs no read, being arithmetic on the word boxes the
reading already returned. When it fires the picture goes through the
photograph path unchanged, OSD with its floor and its second opinion, and if
that names a turn other than the placement's the picture is read again at
that turn and the second reading is kept; if it names the same turn, or
cannot answer, the first reading stands. The reads of a reading set aside
are counted. The reported orientation is then Tesseract's, so that a turn
taken on its verdict is auditable as one.

**Where the placement is not a quarter-turn, `placement_rotation` is None
and nothing changes.** A photograph never has one. `TTB_CORRECT_ORIENTATION`
governs the OSD call and nothing else: a placement turn is applied whether
the setting is on or off, and the gate does not ask when it is off.

**`TTB_MAX_DOCUMENT_READS` comes down from 24 to 16.** ADR 0023 derived 24
as eight pictures times the least a picture costs when its first arm does
not settle it, and counted the orientation call in that least: three. A
placed picture makes no orientation call, so the least is two, the
preprocessed arm and the plain arm, and eight times two is sixteen. It
admits the bourbon's 11 with five reads of margin, more than one worst-case
panel of three arms, and cuts the runaway case from 24 to 16. A ceiling
whose stated reasoning no longer holds is not left standing at the old
number.

## Alternatives considered

### Alternative A: pass `correct_orientation=False` for embedded pictures, as the page path does

The obvious one, and the one the session was asked not to do without
looking. It removes the same seven reads on the bourbon and three on the
mezcal. It also reads the fixture's vertical strip sideways and loses the
three values on it, which `tests/test_artwork_panels.py` shows in nine
failures; reports the method as `disabled`, which is what the setting
being off means and is not what happened; and reads a picture the page
draws turned the way it is stored rather than the way it is shown. The
first of those is the reason. A side strip with its type along it is an
ordinary label shape, the pipeline read it before, and nothing measured
says it should stop.

### Alternative B: decide orientation once per document

One OSD call on the largest picture, applied to all. Pictures inside a
document are independent objects with independent placements, so the
premise is wrong before the cost is counted; and on both filings the
largest picture is the one OSD answers worst about, 180 at 0.03 on the
mezcal and unable to answer on the bourbon's painting. It would have turned
the mezcal upside down.

### Alternative C: keep the OSD call, drop the second opinion

Saves four of the bourbon's seven and two of the mezcal's three. OSD's
verdict was wrong on both panels where the second opinion ran; without it
both are read upside down, which is the failure ADR 0003's floor was set
for after the 2026-08-30 deploy. A rule that keeps the unreliable half of
the pair and drops the half that corrects it is not a saving.

### Alternative D: ask OSD only where the placement reading scored badly

Below `PREPROCESS_SHORT_CIRCUIT_CONFIDENCE`, say. Every panel of the
bourbon scores below it; the rule would fire on all five and save nothing
there.

### Alternative E: a wider gate on sideways type

A simple majority of sideways words would ask about the 1103 by 340 panel,
five tall boxes against three, for an answer of "unable" and one read. Any
sideways line at all would ask about the mezcal, whose two vertical strips
are four such lines beside 230 upright words, for the three reads its
second opinion costs. Neither picture is placed the wrong way up. The gate
chosen fires on the fixture strip alone, and the table in
`_reads_as_sideways` is the evidence.

## Consequences

**Positive.** On the same container, the same three-run method and the same
two filings as ADR 0023: the mezcal from 4 reads to 1 and 3728 ms to 2152;
the bourbon from 19 reads to 11 and 6714 ms to 4267, of which 1 read is
ADR 0026's. Every field outcome, every panel status, every winning arm and
every score on both filings is identical before and after, compared from
the response bodies; the accuracy tier over the twelve synthetic labels is
identical line for line. A picture the page draws turned is now read the way
it is shown, which nothing did before. The fixture's vertical strip is
still read whole.

**Negative.** A placed picture whose type runs along it costs more than it
did: two arms at the placement turn are read and set aside before Tesseract
is asked, seven reads for the fixture strip against five before. On that
fixture the document as a whole still costs less, 11 against 13, because
the other four panels cost one each. The deployed build has not been
re-measured; the figures above are a session container's, and the NFR-1 row
says so.

**Risks accepted.** A raster stored upside down and placed upright, that is
a label affixed upside down on the form, reads at 0 degrees as upright-shaped
garbage rather than as sideways type, so the gate does not fire and OSD is
not asked; before this decision OSD would have been, and on the one axis
where its verdict is worth least (both wrong verdicts on the real filings
were 180). No real filing has shown the case; a reviewer opening the file
sees the label upside down too. A picture with one upright word beside
sideways type is read at the placement turn. A document of eight sideways
strips would cost seven reads each and be cut at sixteen, with the rest
listed as `not_reached`. If a real filing shows a picture the placement
turns wrongly, the placement figure is on the response as `placement` and
the fix is in `_placement_rotation`, not in reinstating the call on every
picture.

## References

- NFR-1 in [03_REQUIREMENTS.md](../03_REQUIREMENTS.md)
- [09_DEPLOYMENT.md](../09_DEPLOYMENT.md) section 9, the session-container measurement of 2026-09-08 and the deployed-build gate it does not replace
- `backend/app/application_form.py`, `_placement_rotation`; `backend/app/ocr.py`, `preprocess`, `_reads_as_sideways`, `_orientation_reads`
- `backend/tests/test_placement_orientation.py`, `test_ocr.py::TestAPlacementTurnCostsNoRead`, `test_read_budget.py`
- OQ-39 in [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md), where the bourbon's three values actually are
- [ADR 0026](0026-nothing-twice-is-not-read-a-third-time.md), the other read this session removed
