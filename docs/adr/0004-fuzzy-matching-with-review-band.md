# ADR 0004: Normalized fuzzy matching with a three-outcome review band

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-20 |
| Author | Kimberly D. Kight |
| Decision reference | D-5 |

## Context

The comparison step decides what the tool is worth. Getting it wrong in either
direction destroys the value: too strict and agents drown in false mismatches,
too loose and a real discrepancy passes.

**Exact string equality is wrong.** Dave Morrison supplies the governing case:
"I had one last week where the brand name was 'STONE'S THROW' on the label but
'Stone's Throw' in the application. Technically a mismatch? Sure. But it's
obviously the same thing. You need judgment."
[Source: Dave Morrison interview]

**But one field genuinely is exact.** Jenny Park on the warning statement: "It
has to be exact. Like, word-for-word, and the 'GOVERNMENT WARNING:' part has to
be in all caps and bold." [Source: Jenny Park interview] This is confirmed by
regulation: 27 CFR 16.21 fixes the text, and 27 CFR 16.22(a)(2) requires the
first two words in "capital letters and in bold type."

So the comparison rules are not uniform across fields. Brand name needs
tolerance; the warning needs none.

**And OCR introduces its own noise.** Extracted text carries recognition errors
that have nothing to do with whether the label is correct.

## Decision

Compare fields using **normalized fuzzy matching** with `rapidfuzz`, returning
**three outcomes** per field: **match**, **needs human review**, or
**mismatch**.

Three field-specific rules apply on top:

1. **Numeric fields** (alcohol content, net contents) are compared numerically,
   not as strings.
2. **The government warning body** is compared for exact text after whitespace
   normalization. Fuzzy tolerance is not applied to it.
3. **The warning prefix** carries a separate check that `GOVERNMENT WARNING:` is
   upper case, reported independently of the body result.

## Alternatives considered

### Exact string equality everywhere

Trivial to implement and to explain, with no thresholds to tune.

Not chosen because it fails Dave's case immediately, and because OCR noise would
make it produce constant false mismatches. It would generate exactly the
experience Dave warns against: "Just don't make my life harder in the process."

### Fuzzy matching with two outcomes, pass or fail

Simpler to present, and gives the agent an unambiguous answer.

Not chosen because it forces the tool to resolve ambiguity that belongs to the
agent. Every threshold choice becomes a policy decision made silently in code:
set it high and `STONE'S THROW` fails, set it low and real discrepancies pass.
The middle outcome is how the system declines to make that call. Dave's words
are the requirement: "You need judgment." The three-outcome design gives the
judgment back to him rather than approximating it.

### A machine-learning classifier over field pairs

Could learn what agents actually treat as equivalent, which is more nuanced than
any threshold.

Not chosen because there is no labeled training data of agent decisions, and no
source in the assignment offers any. It would also make the result harder to
explain, and explainability is what lets an agent overrule the tool (FR-3).

### Fuzzy matching for the government warning too

Would tolerate OCR noise in the longest field on the label, which is where noise
is most likely.

Not chosen because it contradicts the requirement. Jenny is explicit that the
warning must be exact, and the regulation fixes its wording. A fuzzy warning
check would pass "creative" rewordings, which is precisely the abuse she
describes catching: "people try to get creative with the warning all the time."

The cost is real and is accepted: OCR noise in the warning will produce
mismatches that a human would read as correct. That is the right direction to
fail in for this field.

## Consequences

**Positive**

- Dave's case is handled as he described it should be.
- The tool never silently resolves an ambiguous comparison; it routes it to a
  person.
- Every result carries the label value, the application value, and the score, so
  an agent can check the reasoning rather than trust a verdict (FR-3).
- Field-specific rules mean the strictness of each check matches the strictness
  of the underlying requirement.
- `rapidfuzz` is a well-maintained library with no network dependency.

**Negative**

- Two thresholds have to be tuned, and their defaults (95 and 80) are starting
  points rather than derived values. They are marked as assumptions.
- A three-outcome result is more to present in the UI than a binary one, and the
  middle state has to be visually distinct without relying on colour (NFR-5).
- Review rate becomes a metric that matters: too many reviews and the tool saves
  no time, which would defeat the purpose Sarah describes.
- Exact warning matching will produce mismatches caused by OCR noise rather than
  by label defects.

**Risks accepted**

- That the default thresholds are wrong. Unavoidable without measurement; they
  are configurable and will be tuned against the labeled sample set. Tracked as
  OQ-9.
- That the review band is set so wide the tool becomes a sorting mechanism
  rather than a verifier. Detected by tracking review rate as a reported metric
  (see [../07_TEST_STRATEGY.md](../07_TEST_STRATEGY.md) section 3).
- That a false match causes an agent to skip a check. This is the most damaging
  error class in the system, and it is tracked and reported separately from
  overall accuracy for that reason.

## References

- [../03_REQUIREMENTS.md](../03_REQUIREMENTS.md) FR-3 through FR-7
- [../07_TEST_STRATEGY.md](../07_TEST_STRATEGY.md) section 3
- [../06_SECURITY_AND_COMPLIANCE.md](../06_SECURITY_AND_COMPLIANCE.md) section 6.1
- 27 CFR 16.21 and 27 CFR 16.22, quoted in
  [../03_REQUIREMENTS.md](../03_REQUIREMENTS.md) section 1
