# ADR 0018: Alcohol content and net contents are presence checks, and a presence check passes

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-01 |
| Author | Kimberly D. Kight |
| Decision reference | Adds FR-15; narrows [ADR 0013](0013-artwork-derived-values.md), which is amended rather than superseded; keeps FR-11's precedence, FR-3's outcomes and A-12 and A-13 unchanged |

## Context

The author, using the deployed prototype on her own filing:

> Alcohol content and net content needs to also say "match" or "Contains" in
> green when these items are found on the artwork (that is the requirement
> right? to have the volume and alcohol content listed?)

It is the requirement, and she is right. This ADR corrects a design mistake in
ADR 0013.

**What 27 CFR requires.** Fetched from eCFR on 2026-08-30 and quoted rather than
paraphrased in `backend/app/compare.py`:

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

**What the tool was doing with that.** ADR 0013 already used those sections in
one direction: a label with no alcohol content on it is reported as a finding
rather than as nothing to compare. That half was right and is unchanged.

The other direction was thrown away. When the artwork carried `42% ALC BY VOL`,
the tool wrote that value into the application column, compared it against the
picture it came from, and then, correctly, refused to call the agreement a
match. The row read `Read from the artwork` and said the comparison established
nothing.

**The comparison established nothing. The reading established something real.**
The label carries an element 27 CFR requires it to carry. That is exactly the
question an agent is checking, it is answerable from a picture alone, and it is
in no way circular. The circularity was never in the finding; it was in dressing
the finding up as a comparison and printing the same string in two columns.

## Decision

**Where the application declares no value, the row is a one-sided presence
check, and it passes when the label carries the element.**

### 1. A sixth outcome, and it is a pass

`present` sits alongside FR-3's three, FR-2's `not_compared` and FR-14's
`artwork_derived`. It carries a label value, no application value and no score.

No score is deliberate. A score is a similarity between two strings and there is
only one string here; printing 100 beside a one-sided finding would invent an
agreement that was never tested, which is the same error in a different place.

### 2. The chip reads Contains, in the same green as Match, with its own shape

**"Contains" is the stronger claim, not a hedge.** "Match" says two things
agreed. Here one thing was found, and what was found is that the label satisfies
a regulation. Calling it a match would be a smaller, and false, statement about
what happened.

It is styled as a pass because it is one. That makes the shape load-bearing
rather than decorative: Match and Contains share a colour, so under NFR-5's
greyscale rule the word and the silhouette are the only carriers left. Contains
uses a ring holding a dot, which no other outcome uses and which is nothing like
a tick at any size.

If the author prefers the word "Match" on this chip, it is one constant:
`label` on the `present` entry of `PRESENTATIONS` in
`frontend/src/lib/outcomes.ts`. Nothing else keys on the word.

### 3. No application side on the row

The row shows the value found on the label and nothing under it. There is no
"On the application" line, not even one reading "Not supplied".

This is the presentation half of the decision and it is not tidying. The row
used to print the identical string in both columns, because the value had been
read off the artwork and written into the application side, and an agent looking
at two identical values reads a comparison. There was none. One value, one
column, and the chip says which kind of finding it is.

The withdrawal is in `app.verify._declared`, and it is narrow: a value the
artwork supplied stops counting as an application declaration **only** where
that same artwork is the label side. A typed value, a value out of the
document's text layer, and a value read off filed artwork checked against a
photograph the agent supplied are all real declarations and are all compared
exactly as before.

### 4. Both paths exist, and both are tested

Where the application does declare the value, by an agent typing it or by a form
edition that carries it, the row is a two-sided comparison and reports match or
does not match exactly as it always did. FR-11's precedence is untouched:
typed beats the document's text, which beats the artwork.

### 5. Absence is a finding, not "not compared"

Unchanged from ADR 0013 and restated here because it is the other answer to the
same question: a label that does not carry alcohol content or net contents is
reported as a defect against the regulation, whatever the form says, with both
container carve-outs in the reason so an agent can tell a finding from a
violation.

### 6. The tally counts both kinds of check

The summary line reads **"5 of 5 checks passed"**. It counts comparisons and
presence checks together, because both establish something and neither is worth
more than the other on the face of a one-line summary; the chips underneath say
which row was which.

It replaces "3 of 3 verifiable fields match; 2 read from the artwork only",
which was the honest line while those two rows were circular comparisons. They
are not comparisons any more.

## What happens to ADR 0013

**It is amended, not deleted, and it narrows to the case it was built for.**

That case is a value read off the artwork being compared against that same
artwork. After this decision the two presence fields never reach it, because
they are not compared at all. What is left is a field with no presence rule,
read off the artwork, on a submission carrying no photograph: on the fixtures in
`tests/test_artwork_derived_values.py` that is the class or type designation on
a Registry printout whose text layer omits it.

It should be rare. On the author's own filing it does not arise, because that
form states the class or type in item 9. Rare is not never, and the state, its
chip, its shape and its exclusion from the count all stay exactly as ADR 0013
built them. `test_artwork_derived_values.py::test_the_artwork_derived_state_survives_where_it_still_applies`
holds it open.

**Why the two are not alternatives.** A presence check is not a comparison, so it
has nothing to be circular about. `artwork_derived` answers "this comparison
could not have failed"; `present` answers "this label carries what the
regulation requires". They are different sentences about different things, and
the first one only ever needed to exist for rows where the second one does not
apply.

## Consequences

**What gets better.** The two rows an agent looks at most on a document-only
submission stop reporting nothing and start reporting the regulatory finding
that was always available. A COLA document uploaded alone now reads "5 of 5
checks passed" where every one of the five established something, rather than a
qualified count with two rows held out of it.

**What gets worse.** An agent who reads only the colour sees green on a row that
did not compare anything against the application. That is why the word is
"Contains" and not "Match", why the shape differs, and why the row shows no
application side: three independent carriers of the one fact that matters, none
of them colour.

**What is not decided here.** Whether the class or type designation should also
become a presence check. 27 CFR requires it on the label, so the argument would
run the same way; what is missing is the citation work the two fields above have
and a decision about how a class or type designation is recognized on a label at
all, which is the extraction problem [ADR 0015](0015-verify-by-search.md) exists
to work around. It stays out, and it is [OQ-28](../OPEN_QUESTIONS.md).

**What would falsify this.** A compliance agent reading a green Contains chip as
"the application and the label agree". The row shows one value and one column
and says the application declared nothing; if that is still misread, the word or
the styling is wrong, not the finding.
