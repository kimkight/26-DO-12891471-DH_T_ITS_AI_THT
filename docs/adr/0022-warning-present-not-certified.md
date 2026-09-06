# ADR 0022: A warning read too badly to certify is present and not certified, not absent and not a mismatch

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-06 |
| Author | Kimberly D. Kight |
| Decision reference | Amends FR-5's reporting a second time without amending its comparison; extends [ADR 0012](0012-warning-near-miss.md), which handled a difference too small to attribute, to a read too damaged to; touches FR-6 only in that a prefix that was not read is not judged; adds a seventh outcome the way [ADR 0018](0018-presence-checks.md) added the sixth |

## Context

**FR-5's exactness stays.** Jenny Park: "It has to be exact. Like,
word-for-word." 27 CFR 16.21 fixes the wording, [ADR 0004](0004-fuzzy-matching-with-review-band.md)
kept the warning out of the review band, and [ADR 0012](0012-warning-near-miss.md)
kept the comparison exact while routing a difference of one or two characters
to a person. Nothing here loosens any of that.

**And the second real filing breaks on it for a reason none of that covers.**
The bourbon committed as evidence in `samples/real/` ([ADR 0021](0021-real-filings-as-evidence-not-fixtures.md))
carries its government warning on a 1050 by 309 panel that reads at 86.8
confidence. Read panel by panel on 2026-09-06, the body comes back nearly
complete: four of its six lines are the regulation's text exactly. What breaks
it is that printer registration marks and production annotations are
overprinted through the panel. The first word of the prefix reads as a garble
with `WARNING:` intact after it; one clause reads with short fragments where a
word should be; and a run of eight digits arrives as a line of its own after
the statement. The lines that read correctly read at 91 to 96; the two that do
not read at 64 and 69.

**What the tool said about it.** Located by its prefix alone, the statement was
never located, and the row reported that the label carries no government
warning. That is the worst of the answers available about a label a person
would pass at a glance. Had the prefix survived, the comparison would have
failed, correctly, on tokens that are the printer's and not the label's, and
the row would have said the statement does not match word for word, which is
true of that read and of an altered clause alike, and the agent cannot tell
which from a verdict.

**What the reading knows that the text does not.** The tool cannot tell a
garbled word from an altered one by looking at the text: both are a run of
characters the regulation does not contain. It can tell them apart by how
confidently the engine read them. On this filing every line that differs from
the regulation was read below 70 and every line that matches above 90; on the
twelve synthetic labels a compliant statement reads above 90 throughout; and an
altered word set in clean type reads in the nineties like the words around it.
That is evidence about the reading, not about the wording, and it is the only
evidence that separates the two cases.

## Decision

**Locate the statement by what survived, leave letterless lines out of it,
and report a difference the engine read badly, everywhere it differs, as the
statement being present and not certified. Keep the comparison exact.**

1. **Location.** The prefix is looked for first, as always. Failing that, a
   `WARNING` with the body's opening within forty characters after it is the
   prefix with its first word damaged. Failing that, the body's own opening
   locates the statement, provided the statement goes on as the statement does
   within a few lines, so that three ordinary words in a producer's story are
   not taken for it. In both fallbacks the prefix is recorded as illegible:
   its capitalization is not checked, because it was not read, and it is
   reported as unchecked rather than as failed (FR-6). A row with an illegible
   prefix cannot pass.
2. **Letterless lines.** A line with no letter in it is not part of the block,
   inside the statement or after it. No word of 27 CFR 16.21 is letterless, so
   leaving such a line out cannot hide an altered, added or omitted word; it
   can only stop a run of registration digits from failing a statement that
   is otherwise exact. This is the one token filter that is safe, and it is
   safe because it is not a vocabulary filter (alternative A).
3. **A seventh outcome, `not_certified`, for the warning alone.** Where the
   statement is found and does not match, beyond the near-miss threshold, and
   every line of it that is not a run of the regulation's text was read below
   `TTB_WARNING_LEGIBLE_CONFIDENCE`, the row reports the statement as present
   and not certified. Where any differing line was read at or above the floor,
   the difference is the label's and the outcome is the mismatch it always
   was. Where no line differs and the body still does not match, a clause was
   omitted, and that is a mismatch at any confidence. A near miss keeps its
   own outcome. The plain-text path, which has no reading behind it, is
   unchanged: a line with no confidence is never called illegible.
4. **It is a failing outcome, and it is presented as one.** The chip reads
   "Present, not certified", in the review tone because the next action is a
   person's, with its own silhouette, a magnifier, because what it asks is
   "look at the label", which no other outcome asks. It counts as not passed
   in every summary, it outranks a review on a batch row and is outranked by
   a mismatch, and the reason says what was established, what was not, and
   what is being asked. The response carries `prefix_legible`, the counts of
   differing and illegible lines, and `not_certified` beside the existing
   near-miss fields, so the decision is inspectable.
5. **The floor is eighty**, from the one measurement above and the synthetic
   set, configurable as `TTB_WARNING_LEGIBLE_CONFIDENCE`. Neither outcome it
   decides between passes anything, so the cost of the number being slightly
   wrong is which sentence an agent reads, not whether a defective label
   ships; that is the same argument ADR 0012 made for its threshold, and it
   holds here for the same reason.

## Alternatives considered

### Alternative A: compare after removing tokens that cannot belong to the warning

The first option offered, and rejected. A filter that removes every token
outside the regulation's vocabulary cannot be made safe, because a token that
cannot belong to the statement is exactly what an altered wording adds: "some
women should not drink" loses "some" to the filter and passes. That is the
near miss that silently passes, which FR-5 exists to prevent. The safe subset
of the idea, a token that carries no letter at all, is taken as decision 2;
it cannot delete a word because no word is letterless. And on the measured
filing the general filter would have fixed little: the differences there are
garbled real words, GOVERNMENT and CONSUMPTION and ALCOHOLIC, and no filter
restores a garbled word.

### Alternative B: report the noisy read as needs human review, reusing ADR 0012's outcome

Rejected, narrowly. It is the same person's judgement being asked for, but
ADR 0012 defined its outcome as a difference of at most two characters, and
FR-5's own criterion says an altered, added or omitted word is a mismatch and
not a review. A twenty-four-edit difference reported as a review would make the
threshold mean nothing, and an agent reading "needs review" would expect a
diff of a character or two and find a garbled clause. A distinct outcome says
what is different about this case: not the size of the difference but the
quality of the read.

### Alternative C: decide by the fraction of the statement recovered

A similarity ratio: report "present, not certified" when most of the
statement matches. Rejected because it is the similarity band ADR 0004 and
ADR 0012 refused, one level up. A single altered word is a ratio of 0.98,
and FR-5 says it is a mismatch. Confidence is evidence about the reading;
a ratio is evidence about the wording, and the wording is what the
requirement fixes.

### Alternative D: do neither, and record why with the measurement

The third option offered. Rejected because the current answer is the worst
one: it tells an agent the label carries no warning about a label that
carries one, and a reviewer who put the same filing through the tool would
find that before finding the reason. Recording it would have been honest and
it would have left the row wrong.

### Alternative E: per-word confidence rather than per-line

Better evidence, and not taken this session. Tesseract reports confidence per
word and `app.ocr` folds it to a mean per line; separating a garbled word
from the clean words beside it on one line would sharpen the rule. It is more
plumbing than the measurement justifies today, the per-line rule already
separates the measured case cleanly, and a false call in either direction is
between two failing outcomes. Named here so the next person knows where the
precision is.

## Consequences

**Positive**

- On the measured filing the row now says the statement is on the label,
  says which lines could not be read well, and asks the agent to look. The
  outcome is not certified; nothing passed.
- A statement whose prefix OCR damaged is found. Before this it was invisible.
- FR-5's comparison is untouched, and the tests that hold it, an altered word,
  an added word, an omitted clause, hold in the new module too, at low
  confidence and at high.

**Negative**

- A seventh outcome is one more thing an agent learns, and the help text has
  to carry it. It is confined to one field, which limits the cost.
- The floor is one number from one real read. It is configurable and it
  decides between two failing outcomes, but it is a number, and a label
  printed in a face Tesseract reads at 75 throughout would land on the wrong
  side of it. That case is not measured.
- A label that inserts a word of the regulation's own vocabulary on a line of
  its own, at high confidence, is a differing line the substring test does not
  see. The body still fails; the row could read "not certified" where a
  mismatch was deserved if another line read badly. Narrow, failing either
  way, and recorded.

**Risks accepted**

- A confidently misprinted prefix, `GOVERMENT` in clean type, is a mismatch,
  as it should be; a prefix damaged in print rather than in reading is
  indistinguishable from one damaged in reading if it also reads badly, and
  a person is asked to look. That is the right call for the tool to make.
- The per-line substring test treats a line that is a run of the statement as
  clean even where it is a run from the wrong place. An omitted clause still
  fails, because the body comparison is unchanged; only which of two failing
  outcomes is reported could be affected.

## References

- The measurement: `docs/09_DEPLOYMENT.md` section 9, 2026-09-06, on the
  filing committed as evidence in `samples/real/` (ADR 0021).
- [FR-5](../03_REQUIREMENTS.md) and [FR-6](../03_REQUIREMENTS.md), as amended.
- [ADR 0012](0012-warning-near-miss.md), the near miss; [ADR 0004](0004-fuzzy-matching-with-review-band.md),
  the review band the warning stays out of; [ADR 0018](0018-presence-checks.md),
  the last outcome added and the shape this one follows.
- `backend/app/warning.py`, `backend/app/parse.py`, `backend/app/verify.py`;
  `backend/tests/test_warning_legibility.py`;
  `frontend/src/__tests__/warningNotCertified.test.tsx`.
