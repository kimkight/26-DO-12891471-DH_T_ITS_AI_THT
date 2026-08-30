# ADR 0012: A near miss on the government warning goes to a person, not to a verdict

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-29 |
| Author | Kimberly D. Kight |
| Decision reference | Amends FR-5's reporting without amending its comparison; extends [ADR 0004](0004-fuzzy-matching-with-review-band.md), which excluded the warning from the review band; depends on [ADR 0010](0010-embedded-label-artwork.md) for the evidence |

## Context

**FR-5's exactness is sourced, and it stays.** Jenny Park: "It has to be exact.
Like, word-for-word." 27 CFR 16.21 fixes the wording of the statement, so there
is nothing for an applicant to have declared differently and nothing for a
similarity score to be tolerant about.
[ADR 0004](0004-fuzzy-matching-with-review-band.md) put every other field into a
match / review / mismatch band and deliberately kept the warning out of it.

**And the author's own document breaks on that exactness for the wrong reason.**
The label artwork embedded in their COLA filing, read on 2026-08-29 through the
pipeline [ADR 0010](0010-embedded-label-artwork.md) added, OCRs the government
warning with **exactly one character wrong**: `MPAIRS` for `IMPAIRS`. Everything
else in the statement is correct. Reported as a mismatch, that tells an agent
their label is defective. The truth is that the scan is imperfect.

The two failures are indistinguishable in the result as it stood. "The statement
text does not match 27 CFR 16.21 word for word" is equally true of one dropped
character and of a missing clause, and the difference between those two is the
whole of the agent's decision.

## Decision

**Keep the comparison exact. Change what a very small difference is reported
as, and show the difference.**

- The body still has to be identical to 27 CFR 16.21 after whitespace
  normalization to be a **match**. `body_matches_regulation` is that comparison
  and nothing else, and it is unchanged.
- A difference of at most `TTB_WARNING_NEAR_MISS_EDITS` single-character edits
  is reported as **needs human review**, with the exact character-level
  difference shown.
- Anything beyond that is still a **mismatch**, and the difference is shown for
  that too, because it is evidence either way.
- A capitalization failure on the prefix is **never** a near miss. It is a
  defect a person caught on a real submission (FR-6, Jenny Park), it is not
  something OCR produces from a compliant label, and it is reported as the
  mismatch it is even when the body is a near miss.

**This is not a fuzzy match, and the distinction is the point.** A fuzzy match
would let a label through on a similarity score. Nothing here passes anything: a
near miss is one of the two *failing* outcomes, and what separates it from a
mismatch is which sentence the agent reads and whether they are handed the
difference to look at. FR-5's own criterion, "given a warning with altered,
added, or omitted words, then the outcome is mismatch, not needs human review",
is about a warning the tool can see is altered. A one-character difference at
this length is not something the tool can attribute, and saying it is defective
would be the tool overstating what it knows in exactly the direction OOS-8 and
FR-6 exist to prevent.

### The threshold, and why two

`TTB_WARNING_NEAR_MISS_EDITS` defaults to **2**. The defence, in order of
weight:

1. **Neither outcome passes.** This is the load-bearing one. The cost of the
   number being slightly wrong is which sentence an agent reads and which shape
   the card takes, not whether a defective label ships. That is what makes a
   threshold defensible here at all, where a fuzzy-match threshold on the same
   field would not be.
2. **One is the observed case.** The author's artwork differs by exactly one
   character. A threshold of 1 would cover it and nothing else; two gives one
   character of headroom for the double substitutions OCR also produces, which
   the same pipeline demonstrably makes (`rn` read as `m`, and a neighbouring
   character lost with it).
3. **Two is below the length of any word in the statement.** 27 CFR 16.21's
   shortest words are `a`, `of`, `to`. Removing `a` costs two edits, the letter
   and the space beside it, which is the largest wording change two edits admits,
   and it is one an agent should see rather than one that should be hidden. No
   whole word longer than that can be added, removed or substituted within two.
4. **Above two, the sentence starts to change rather than its rendering.** Three
   edits begins to admit a substituted short word, and a substituted word is a
   difference in what the label says rather than in how it was read. That is the
   line this threshold is drawn at.

The block is 232 characters, so two edits is under 1 percent of it. The number is
a setting rather than a constant because it is a judgement about OCR quality
rather than a measurement of it, and the OCR quality of a real filing is
[OQ-21](../OPEN_QUESTIONS.md#oq-21) and
[OQ-24](../OPEN_QUESTIONS.md#oq-24) territory (NFR-11).

### The difference itself

Computed character by character with `difflib.SequenceMatcher`, not word by
word. `MPAIRS` against `IMPAIRS` is one missing character, and a word-level diff
would report the whole word as changed and hide which kind of difference it was.
`autojunk` is off: it otherwise treats any character appearing in more than
1 percent of a long sequence as junk, which over this sentence means the spaces
and most vowels.

Each run is marked by **text as well as by styling**: `<del>` and `<ins>`, each
carrying a visually hidden "missing:" or "extra:", with a legend under the block
saying in words what each one is. NFR-5's greyscale rule applies here exactly as
it does to the outcome chips.

## Alternatives considered

### Alternative A: loosen FR-5 to a similarity band

Rejected, and it is the alternative this ADR exists to refuse. It would make a
label with a genuinely altered word pass on a score, which is what Jenny's
"word-for-word" rules out and what ADR 0004 already declined for this field. The
change made here is orthogonal: the comparison stays exact, and only the
reporting of a difference too small to attribute changes.

### Alternative B: fix the OCR instead

Rejected as unavailable rather than as wrong. It is the better answer, and this
project cannot reach it: the misread is Tesseract's, on artwork read at the
resolution the file carries, and improving it means a different engine, which is
SG-2 and carries the FedRAMP and data-handling questions already recorded there.
This is what to do in the meantime, and it is honest about being that.

### Alternative C: report the mismatch, and let the agent notice the diff

Rejected because it inverts the burden. A mismatch is a verdict, and an agent
working through a batch of results acts on verdicts. Putting the difference on
the card while still calling it a mismatch would leave the tool asserting
something it cannot support and relying on the agent to disbelieve it.

### Alternative D: a word-level diff

Rejected: see above. It would report `MPAIRS` as a changed word, which is the
information the agent already has.

## Consequences

**Positive**

- The author's own document stops reporting a compliant warning as defective.
- An agent is handed the actual difference, which is what the decision needs.
- FR-5's comparison is untouched, so nothing that used to fail now passes. The
  existing FR-5 fixtures are unchanged in outcome, and that is asserted.

**Negative**

- A third shape on the warning card, which is more for an agent to read. It
  appears only when there is a difference to show.
- A real defect of one or two characters now reads as needs review rather than
  as mismatch. It is still not a pass, the difference is on screen, and the
  reason says explicitly that this is not a match.

**Risks accepted**

- **A meaning-changing difference could fit inside two edits.** The mitigation
  is that nothing passes: the agent is shown the exact characters and asked to
  judge. The residual risk is an agent who reads "needs review" as "probably
  fine" and does not look. That is the same risk ADR 0004's review band already
  carries on every other field, and it is why the reason line says "This is not
  a match" in those words.
- **The threshold is a judgement.** It is a setting, and the reasoning above is
  written down so that moving it is a decision rather than a tweak.

## References

- Jenny Park interview, "It has to be exact. Like, word-for-word."
- 27 CFR 16.21 and 16.22, quoted verbatim in
  [03_REQUIREMENTS.md](../03_REQUIREMENTS.md) section 1, retrieved from eCFR on
  2026-08-20
- The author's evidence, 2026-08-29: the embedded label artwork OCRs the warning
  with one character wrong
- [ADR 0004](0004-fuzzy-matching-with-review-band.md), which kept the warning out
  of the review band
- [ADR 0010](0010-embedded-label-artwork.md), which produced the reading
- [FR-5](../03_REQUIREMENTS.md), amended in its reporting and not in its
  comparison
- `backend/app/warning.py`, `backend/tests/test_warning_near_miss.py`,
  `frontend/src/__tests__/warningNearMiss.test.tsx`
