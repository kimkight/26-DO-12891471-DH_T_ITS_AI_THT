# ADR 0026: A coloured picture whose colour arm and preprocessed arm both read nothing at all is not read a third time

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-08 |
| Author | Kimberly D. Kight |
| Decision reference | NFR-1, FR-1; narrows [ADR 0014](0014-colour-as-an-ocr-candidate.md)'s third arm on the coloured source by one case |

## Context

The 1950 by 862 panel of the bourbon filing in `samples/real/` is a painting
with one line of type 24 pixels tall along its bottom edge, and on the
session container's Tesseract 5.3.4 it reads as no text at all: the colour
arm returns no words, the preprocessed arm returns no words, and the plain
arm returns no words, each at full resolution, for about a second of engine
time after the orientation call, and the response reports the panel as
`no_text`. The three values on that line, the class or type, the alcohol
content and the net contents, are not found by any arm, and OQ-39 records
why: the type is legible and reads at 88.0 cropped to its own band, and
what fails is the layout analysis, which does not find one line of text on
a picture. This decision does not touch that. It stops paying for arms
that will find nothing.

**Two cautions, both load-bearing, both taken.** The first: a read of
nothing is not a low read. The bourbon's 1350 by 300 panel reads 44.7
preprocessed and then 89.9 plain, and the brand name is on the plain read;
a rule that skipped arms under a confidence floor would drop it. The rule
has to be written on "nothing came back", which is the word count, never on
a confidence. The second: low contrast is a known limit and not a thing to
optimise around. Section 9 of the deployment notes names three labels the
reader reads poorly, pale mint on white, gold on near-black and pale pink
on deep purple, and the preprocessed arm exists because the plain read of
such a label can return little. A rule that abandoned those would be the
wrong rule.

**What each arm is for on a coloured source, restated from ADR 0014.** The
colour arm reads the untransformed pixels, because it is the one rendering
that cannot have lost an ink class before Tesseract saw it. The preprocessed
arm is the adaptive threshold, the one local operation in the pipeline. The
plain arm, the grayscale, runs on a coloured source to compete with a
*confident* read of a transformed image that may have dropped an ink class
without any surviving word scoring lower for it. Where the preprocessed
read found nothing there is no confident transformed read to compete with;
and the colour arm has already read the pixels the plain arm is a weighted
mean of.

**And the grayscale cannot see what the colour arm could not.** The plain
arm is one channel, a weighted mean of three; the contrast between any two
inks in a mean of channels can never exceed the contrast in the channel
that separates them best. Tesseract, handed a three-channel image, runs its
threshold on each channel and keeps the best. So for any two-tone type the
colour arm has already had at least the contrast the plain arm will get.

**Measured, 2026-09-08, before choosing.** Every arm at full resolution,
exactly as `extract_text` reads them, over the three low-contrast shapes at
24 and 46 pixel type, each clean, under an illumination gradient, under
glare and at two levels of contrast loss; the three-class colour fixture
under the same; and the painting. Thirty cases. Selected rows, mean word
confidence with the word count in brackets:

| case | colour | preprocessed | plain |
| --- | --- | --- | --- |
| pale mint on white, 24 px | 95.1 (12) | 88.0 (12) | 95.2 (12) |
| gold on near-black, 24 px | 95.2 (12) | 15.7 (14) | 95.3 (12) |
| pale pink on deep purple, 24 px | 95.2 (12) | 26.4 (11) | 95.2 (12) |
| pale pink on deep purple, 46 px, gradient | 80.7 (9) | 17.1 (7) | 0.0 (0) |
| three-class fixture, gradient | 68.1 (16) | 0.0 (0) | 78.4 (14) |
| three-class fixture, glare | 80.7 (23) | 18.2 (4) | 89.1 (18) |
| bourbon painting, 1950 x 862 | 0.0 (0) | 0.0 (0) | 0.0 (0) |

In all thirty, the colour arm read every case the plain arm read; where
the colour arm read nothing, which is the painting alone, every arm read
nothing. The plain arm still earns its place where the colour arm read
*something* badly, as the two fixture rows show, and those are cases the
rule below leaves exactly as they were.

The same fixtures degraded into a photograph lose their chroma and take the
monochrome path, and there v1.0.1's own finding stands: the preprocessed
arm reads zero words where the plain arm reads them all, on the gold and
the pink at 46 pixels and on the three-class fixture. That path is not
touched.

## Decision

**On a coloured source, when the colour arm and the preprocessed arm have
both returned no words at all, the plain arm is not read.** The test is on
words, in `_needs_the_plain_read`; a read of anything, however badly
scored, is a read the comparison runs for. `ReadPath.plain_confidence` is
null in that case, as it is when the comparison was settled by the short
circuit, so the response says the arm never ran rather than that it scored
zero. The preprocessed arm is not touched by this rule and still runs at
full resolution on the coloured source; the monochrome source is not
touched at all.

## Alternatives considered

### Alternative A: skip both transforms when the colour arm reads nothing

The cheaper rule, and on the thirty cases it would have lost nothing
either: no case had the colour arm read nothing while a transform read
something. Not chosen, because its argument is only that no case was
found. The preprocessed arm is the one local threshold in the pipeline and
the illumination gradient is what a local threshold exists for; on the
monochrome path the measurements show a transform arm at zero words beside
another arm reading every word, which is the shape of failure this rule
must not produce on the coloured path by argument alone. The plain arm has
the structural argument above; the preprocessed arm does not. On the
painting the difference is one read of about 200 ms.

### Alternative B: a reduced-scale probe of the second and third arms

`extract_text` already has the shape: the 180-degree second opinion scores
at half resolution and repeats at full resolution when the reduced read
returns nothing. That repeat is the reason a probe is wrong here. It exists
because type too small to read at half scale reads as nothing at half
scale, and a probe that reads nothing on a 24 pixel line, which is 12
pixels at half scale, would then have to be repeated at full resolution to
be trusted, which is the read it was meant to save. And it adds reads to
the count the budget is written in.

### Alternative C: a confidence floor under the arms

Drops the 1350 by 300 panel, preprocessed 44.7 and then plain 89.9 with the
brand name on it. The first caution.

### Alternative D: leave it

One read and about 300 ms on the bourbon, on a panel reported `no_text`
either way. Chosen against because the read is demonstrably reading
nothing, and NFR-1 is measured in the seconds it costs.

## Consequences

**Positive.** The painting costs two arms instead of three; with ADR 0025's
orientation call gone as well it costs two reads instead of four. Nothing
about what is found on it changes, because nothing was found on it by any
arm. Every other panel on both filings reads exactly as before, arm for arm
and score for score. On a coloured label that reads at all the rule never
fires.

**Negative.** The bourbon's three values are still not found, the panel is
still `no_text`, and OQ-39 is still open; this decision makes that outcome
cheaper, not better.

**Risks accepted.** A coloured label whose type only the plain grayscale
can read while both the colour arm and the adaptive threshold return
nothing at all. Not seen in thirty cases, and argued impossible for two-tone
type above; if a real filing shows one, the rule is one condition in
`_needs_the_plain_read` and the case belongs in `tests/test_colour_arm.py`
beside the ones that set it.

## References

- NFR-1 in [03_REQUIREMENTS.md](../03_REQUIREMENTS.md)
- [ADR 0014](0014-colour-as-an-ocr-candidate.md), why the third arm exists
- [09_DEPLOYMENT.md](../09_DEPLOYMENT.md) section 9, the low-contrast labels and this session's measurement
- OQ-39 in [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md), why the painting's line is not found
- `backend/app/ocr.py`, `_needs_the_plain_read`; `backend/tests/test_colour_arm.py::TestNothingTwiceIsNotReadAThirdTime`
