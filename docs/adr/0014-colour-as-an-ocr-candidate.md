# ADR 0014: The colour image is an OCR candidate, and a tie on confidence is broken by what was read

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-30 |
| Author | Kimberly D. Kight |
| Decision reference | Extends [ADR 0003](0003-local-ocr-default-bedrock-optional.md) and assumption [A-15](../ASSUMPTIONS.md#a-15); changes no requirement |

## Context

v1.0.1 stopped trusting preprocessing to be an improvement. It reads the
adaptively thresholded image, and unless that read comes back confident it reads
the plain upright grayscale as well and keeps whichever scored higher on mean
word confidence. That decision was right and the measurement behind it holds:
over the twelve-label sample set degraded into a photograph-like fixture, the
thresholded image read zero words where the plain grayscale read all sixty-two.

Both candidates are grayscale. Neither is the image the file holds.

**The submission that made that matter.** The author submitted their own mezcal
COLA document to the deployed build on 2026-08-30. The label is printed in more
than two tones: a black government warning on a light ground, a light brand and
body copy on a dark green ground, and the alcohol content in a third ink between
them. The read came back at high confidence with the alcohol content missing
entirely. Measured on that artwork, upright:

| Image variant | Words | Mean word confidence | `42% ALC BY VOL` |
| --- | --- | --- | --- |
| Colour | 257 | 89.1 | read |
| Grayscale | 106 | 89.9 | not read |

**Two separate problems are in that table, and the second is the harder one.**

The first is that a threshold, adaptive or global, separates two luminance
classes and not three. On a label carrying dark-on-light *and* light-on-dark
text on one ground, one of the two always dissolves into the background. Filed
label artwork is routinely coloured this way, so this is the normal case for the
feature rather than an edge case.

The second is that **mean word confidence cannot detect it.** That signal
measures how sure Tesseract is of the words it read. It says nothing whatever
about the words it did not read, because a word that was never read contributes
no confidence to lower. So the variant that lost two of the five required fields
scored *higher* than the variant that kept them, by 0.8 points, and every check
in the pipeline agreed the read had gone well. That is why the defect survived
two deploys.

## Decision

**One: the colour image is a first-class OCR candidate, and on a coloured source
it is read first.**

`preprocess` produces three images rather than two: the thresholded one, the
plain upright grayscale, and the scaled, upright colour image, which is to say
the pixels the file holds. On a source with colour to lose, the colour image is
read first and a read that clears `PREPROCESS_SHORT_CIRCUIT_CONFIDENCE` ends the
comparison there. Otherwise all three are read and ranked.

The order is the decision, not an implementation detail. The failure being
guarded against is a confident read of whatever survived a transform, so a
confident read *from* a transform is not evidence that nothing was lost. The
untransformed pixels are the only rendering that cannot have lost an ink class
before Tesseract sees them, so they go first and the transforms earn their place
against them.

**Two: whether a source has colour to lose is measured, not assumed.**

A three-channel array is not a colour image. An exact channel comparison would
call every photograph ever submitted one, because sensor noise is per-channel,
and each would buy a full Tesseract pass to learn nothing. What is measured is
chroma, `max(R,G,B) - min(R,G,B)` per pixel:

| Image | Highest chroma | Share of pixels at or above 32 |
| --- | --- | --- |
| The twelve rendered sample labels | 0 | 0.000 % |
| A sample label degraded to a photograph-like fixture | 30 | 0.000 % |
| The three-class colour fixture | 140 | 84.381 % |

A source counts as coloured when at least one percent of its pixels carry chroma
of 32 or more. The gap between the two clusters is 0.000 percent against 84
percent, which is not a threshold on a knife edge. The consequence that matters
for NFR-1 is that every image in the sample set, and every grayscale scan and
fax, takes the v1.0.1 path at the v1.0.1 cost.

**Three: mean word confidence still ranks, and a tie on it is broken by how much
text was recovered.**

Two arms whose mean confidences differ by more than `EQUAL_CONFIDENCE_BAND`, one
point, are ranked by confidence exactly as v1.0.1 ranked them. An arm that read
more words but scored materially lower still loses; that rule is asserted in
`backend/tests/test_colour_arm.py` so it cannot be quietly inverted.

Two arms *inside* that band are, on this evidence, equally confident about
whatever each of them read, and the only question left is which of them read
more. That is the case the table at the top of this ADR describes, and it is the
case mean confidence is structurally unable to decide.

One point is the band because it is above both measured gaps and below every gap
the v1.0.1 comparison actually has to settle. Re-measured over the twelve-label
sample set on 2026-08-30: on the clean renderings the comparison never runs at
all, because all twelve short-circuit on the preprocessed read; on the same set
degraded to a photograph-like fixture, where both arms are read every time, the
two are never closer than 29.0 points. The band fires on no case in that set.

| Measurement | Colour | Grayscale | Gap | Which lost a field |
| --- | --- | --- | --- | --- |
| The author's mezcal artwork | 257 words, 89.1 | 106 words, 89.9 | 0.8 | Grayscale |
| The three-class fixture | 93 words, 95.613 | 87 words, 95.609 | 0.004 | Grayscale |

## Alternatives considered

### Keep ranking on mean word confidence alone

This is what the brief for this change asked for, and it does not work on the
brief's own figures. The grayscale read scores 89.9 against the colour read's
89.1 while being the one that lost `42% ALC BY VOL`, so adding the colour arm
and ranking strictly by mean confidence would add a Tesseract pass and change no
answer. Rejected on the measurement rather than on preference.

### Rank by word count, or by total confidence mass

Word count hands every comparison to whichever rendering hallucinated the most
text, which is the failure v1.0.1's ranking exists to prevent. Total confidence
mass, words multiplied by mean, is word count wearing a hat: a hundred junk words
at 20 outscores fifty good ones at 95. Both discard a signal that works in order
to fix a case where it does not.

### Read the colour image only when the grayscale reads badly

The premise is exactly the one this ADR rejects. The grayscale read of the
author's artwork does not read badly; it reads at 89.9 having lost a required
field. A gate on the score cannot open on a failure the score cannot see.

### Merge the lines from all three reads

Tempting, and it discards the one thing the arms are for. Three reads of one
picture disagree about the same words, and a merge has to decide which spelling
of `GOVERNMENT WARNING` is the real one; that is a harder problem than choosing
a rendering, and it would put fabricated composite text into a compliance
comparison. Rejected on FR-5: the warning is compared character by character
against 27 CFR 16.21, and a sentence assembled from three readings is not a
sentence anybody printed.

### Segment the label by colour and read each region

The general form of the right answer, and out of proportion to a prototype. It
needs a clustering step, a region merge, and a way to order the recovered text
back into lines, all of it unmeasured. The colour arm gets the measured cases
for one Tesseract pass. Recorded here as the direction, not taken.

## Consequences

- A coloured label that reads cleanly now costs **one** Tesseract read where the
  author's artwork paid two. Measured on a session container with the same
  document shape: 1512 / 1563 / 1547 ms before, 1526 / 1425 / 1587 ms after, at
  one OCR pass either way.
- A coloured label that reads poorly costs three reads, on an image whose own
  pixels have already read badly. That is the case where a transform has
  something to contribute, and it is bounded: three, never more.
- Nothing that carries no colour pays anything. The sample set, the accuracy
  tier and every grayscale scan take the v1.0.1 path unchanged.
- `read_path` gains `colour_confidence` and `decided_by`, so an agent can see
  which rendering produced their result and why it won. `ocr_passes` still
  counts pictures; `tesseract_reads` is added beside it, because every arm here
  happens inside one pass and a release that tripled the engine invocations
  while the pass count held at 1 would be the same mistake the 2026-08-30 timing
  finding was.
- The band is a judgement about a measurement rather than a measurement. Two
  cases set it and both are the same phenomenon. It is stated as a named
  constant with its evidence beside it, and the case where it decides is
  reported as `decided_by: "coverage"` rather than hidden.

## References

- [ADR 0003](0003-local-ocr-default-bedrock-optional.md), which this extends
- [../ASSUMPTIONS.md](../ASSUMPTIONS.md) A-15
- [../03_REQUIREMENTS.md](../03_REQUIREMENTS.md) FR-1, FR-5, NFR-1
- `backend/app/ocr.py`, `backend/tests/test_colour_arm.py`
