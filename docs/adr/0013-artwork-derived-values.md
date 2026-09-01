# ADR 0013: Values read off the label artwork are filled in, and never called a match

| | |
| --- | --- |
| Status | Accepted, amended 2026-09-01 by [ADR 0018](0018-presence-checks.md) |
| Date | 2026-08-30 |
| Author | Kimberly D. Kight |
| Decision reference | Extends [ADR 0010](0010-embedded-label-artwork.md), which put the artwork into the application side; adds FR-14; keeps FR-11's precedence and FR-7's outcomes unchanged |

## Amendment, 2026-09-01

**Two of the rows this decision was written about are not comparisons any more,
so they never reach the state it invents.** [ADR 0018](0018-presence-checks.md)
makes alcohol content and net contents one-sided presence checks wherever the
application declares no value: the row reports that the label carries the
element 27 CFR requires, in green, with no application side at all.

What that corrects is a mistake in this document rather than in its reasoning.
The argument below is right that comparing a value against the picture it was
read from establishes nothing. What it did not notice is that the *reading*
established something: the label carries a mandatory element. Section 3 of this
ADR says so in as many words, under "Presence remains an independent finding",
and then reports only the absent case. ADR 0018 reports the present case too.

**What stands, unchanged.** The `artwork_derived` state itself, its word, its
silhouette, its absent score, its source line on the row, its exclusion from the
count, and the rule that only agreement is ever relabelled. So does the
provenance rule below: it keys on where a value came from and not on a field
name, which is exactly why it narrows cleanly rather than needing rewriting.

**What it narrows to.** A field with no presence rule, read off the artwork, on
a submission carrying no photograph. On the fixtures that is a class or type
designation on a Registry printout whose text layer omits it; on the author's
own filing it does not arise at all, because that form states the class or type
in item 9. Rare is not never, and
`tests/test_artwork_derived_values.py::test_the_artwork_derived_state_survives_where_it_still_applies`
holds the state open.

**What is superseded.** Two acceptance criteria on FR-14, named in
`docs/03_REQUIREMENTS.md`: the one that made a presence field's row
`artwork_derived`, and the one that phrased the summary line as "3 of 3
verifiable fields match; 2 read from the artwork only". The line now reads "5 of
5 checks passed" and counts both kinds of check.

The rest of this document is left as it was written on 2026-08-30.

## Context

[ADR 0010](0010-embedded-label-artwork.md) established that a COLA filing
carries its own label artwork, and that three of the five values this tool
compares are not items on TTB F 5100.31 at all (assumption A-17): the class or
type designation, the alcohol content and the net contents are printed on the
artwork affixed to the application rather than in a numbered box. It filled
those values from the artwork, and it made the label side of a check fall back
to that same artwork when the agent uploaded no photograph of their own.

Both halves are right on their own. Together they produce a row that compares a
value against the picture it was read from.

**Why filling them is not optional.** Sarah Chen's case for the tool is that
agents "spend half their day doing what's essentially data entry verification".
Asking an agent to hand-type two values off a document the tool has already read
puts that data entry straight back. The batch path decides it: SC-3 exists
because importers submit "200, 300 label applications" at once, and a batch takes
COLA documents with no agent present to type anything. A rule that leaves those
values empty hollows out the feature Sarah named as the unmet need.

**Why calling the result a match would be worse than leaving them empty.** Dave
Morrison is the reason this tool has a human-review band instead of a pass or a
fail, and Jenny Park rejected a real filing over title case. These are agents who
act on what the panel says. A comparison of a value against the artwork it came
from always agrees, so a green match chip there is structurally incapable of ever
saying anything else. That is not a weak signal; it is a signal with no
information in it, presented in the same shape as the four signals that do carry
information. It is a false assurance, and it is how a tool loses a sceptical user
permanently.

## Decision

**Fill them, and never call them a match.** Three conditions, all of them
acceptance criteria on FR-14.

### 1. Its own outcome state, excluded from the match tally

A fifth outcome, `artwork_derived`, sits alongside FR-3's three and FR-2's
`not_compared`. It is not a verdict about agreement. It says the value was read
off the artwork and that there was nothing independent to check it against.

The summary line stops saying "5 of 5 fields match", which counted rows that
could not have come out any other way, and says what is true:

> 3 of 3 verifiable fields match; 2 read from the artwork only

Where nothing was artwork-derived, which is every submission carrying a
photograph, the qualifier disappears and the line reads as it always did.

The state carries **text and shape before colour**, as NFR-5 requires of the
other four: the words "Read from the artwork", a picture-frame silhouette that no
other outcome uses, and a violet that belongs to none of the good, attention or
bad family the other four form. Removing the colour entirely leaves the state
fully legible, which is the test NFR-5 sets.

### 2. The source is stated on the row, not in a footnote

The row carries its own `Source` line reading **"Label artwork (same source as
the label)"**, and one sentence saying what that means. An agent scanning five
results has to see why one of them is different without reading anything else on
the page. A caveat at the bottom of the panel is read by the people who already
understood it and missed by everyone else.

"Label artwork" alone was already on any row whose value came off a picture,
including rows checked against an independent photograph. The parenthetical is
the whole of the addition: on this row the artwork is *also* the label side.

### 3. Presence remains an independent finding

27 CFR requires alcohol content and net contents on the label whatever the
application form says. Whether the artwork carries them is a question about the
artwork alone. It is answerable from a picture lifted out of a filing exactly as
well as from a photograph of a bottle, and it stays a real result when the
comparison beside it has become a comparison of a value with itself.

**This is the half of the check that was never circular, and it is the reason
reading the artwork is worth doing at all.** So absence is reported as the
finding FR-1 already makes it rather than folded into "not compared", which is
what the row used to say when neither side stated a value.

Three sections govern it, fetched from eCFR on 2026-08-30 and quoted rather than
paraphrased:

- 27 CFR 5.63(a)(3) requires alcohol content on a distilled spirits label, and
  5.63(b)(2) requires net contents "(which may be blown, embossed, or molded into
  the container as part of the process of manufacturing the container)".
- 27 CFR 4.32(b)(3) requires alcohol content and 4.32(b)(2) net contents on a
  label affixed to a wine container, with no container carve-out.
- 27 CFR 7.63(a)(5) repeats the container carve-out for malt beverage net
  contents, and 7.63(a)(3) requires alcohol content on a malt beverage only "for
  malt beverages that contain any alcohol derived from added nonbeverage flavors
  or other added nonbeverage ingredients (other than hops extract) containing
  alcohol".

Both carve-outs are stated in the finding's own reason text, because an agent
reading it needs to know when absence is not a defect. The tool recommends and
the agent judges (FR-3); it does not conclude a violation from a picture of a
flat label.

### 4. FR-11's precedence is unchanged

A typed value still beats a value read out of the document's text, which still
beats a value read off the artwork. That is Dave Morrison's override and it costs
nothing. A row whose application value came from anywhere but the artwork is
compared normally and reported normally, whatever the label side was read from.

## The rule keys on provenance, not on a field name

The circularity condition is: **the application value was read off label artwork
embedded in the uploaded document, and that same artwork is standing in as the
label side.** It is not a list of field names.

Two consequences are deliberate.

It covers whatever fields actually fell that way on a given filing. On the
author's own document that is the alcohol content and the net contents the
decision names, and the class or type designation alongside them, which A-17 says
the form does not carry either. Restricting the rule to two named fields would
have left a structurally guaranteed green chip on the third, which is the exact
thing this ADR exists to remove.

And it does **not** fire when the agent supplied a photograph. Comparing a
reading of that photograph against a reading of the filed artwork is two
pictures. That is a real comparison, it is reported as one, and on the batch path
(ADR 0009 pairs every row's document with a label image) it is the only thing
that can happen: a batch row cannot be artwork-derived.

## Only agreement is relabelled, and that is the safety argument

Reading one picture twice can manufacture agreement. It cannot manufacture a
mismatch, a review, or a not-found. So the overlay replaces a **match** and
nothing else, and every other outcome on a circular row is left exactly as the
comparison found it.

That is what keeps the two real findings intact on a document-only submission:
a mandatory element missing from the artwork reaches the agent as the finding
27 CFR makes it, and the A-12 proof contradiction below reaches them as the
review A-12 fixes for it.

The score goes with the outcome. A similarity of 100 between a string and itself
is arithmetically true and tells an agent nothing, and printed beside this row it
would read as strong evidence of exactly the thing that was not established. The
row carries no score at all.

## The one genuinely non-circular internal check

For spirits, a label stating both a percentage and a proof states the same number
twice, and 27 CFR 5.65 fixes the relation between them. Whether they agree is a
property of that label alone: it needs no application value, it is not weakened
by the application being silent, and it cannot be manufactured by reading one
picture twice.

FR-7 and A-12 already required this cross-check. What they did not say was what
to do when there is no application value beside it, and the answer used to be
that the row reported "not compared" and the contradiction went unmentioned. It
now runs **before the application side is considered at all**, so a label that
contradicts itself is reported whether or not anything was declared against it.

**Its outcome is unchanged: needs human review.** FR-7's third bullet and A-12
both fix that, and both give the reason: a proof that is not twice the ABV
"indicates an internal inconsistency on the label itself", which is a person's
call. The author's brief of 2026-08-30 described this as reporting "a mismatch",
in a sentence whose contrast was with `artwork_derived` rather than with
`needs_review`; the substantive requirement in it, that a disagreement is a real
defect and is never absorbed by the new state, is met exactly. Changing the
outcome itself would mean amending FR-7, A-12 and UAT row 21 in
docs/07_TEST_STRATEGY.md, which is an assumption change rather than a code
change. It is recorded as [OQ-25](../OPEN_QUESTIONS.md) so the author can make it
deliberately.

## Consequences

**What gets better.** A COLA document uploaded on its own now returns five
populated rows instead of two empty ones, and every one of them says what it is.
An agent can tell at a glance which findings are about the label alone, which are
real comparisons, and which are neither. The batch path gets the same values with
none of the caveat, because every batch row has an independent photograph.

**What gets worse.** A submission that used to read "5 of 5 fields match" now
reads "2 of 2 verifiable fields match; 3 read from the artwork only", which is a
less satisfying number. It is the true one. An agent who wants the other number
has a way to get it that the interface states on the row: upload a photograph of
the bottle, or type the value from the filing.

**What is not decided here.** Whether the batch path should accept a row with a
document and no image, which today it refuses (ADR 0009). Nothing in this ADR
needs it, and adding it would make batch rows artwork-derived, which is a
different decision with a different argument. It stays out.

**What would falsify this.** A compliance agent saying that a check of filed
artwork against the filing it came from is what they actually want and that they
read it as a verification. Nothing in the interviews says so; Dave Morrison's and
Jenny Park's accounts both point the other way.
