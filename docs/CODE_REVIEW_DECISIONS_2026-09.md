# Decisions on the code review, 2026-09-01

Author's decisions on the eight questions raised by the v1.2.0 code review
([CODE_REVIEW_2026-09.md](CODE_REVIEW_2026-09.md)) and the secondary
two-document test. Hand this to the session that does the work; these are
settled, not open.

**The frame for every one of them.** This repository is an assignment. The
panel is assessing software architecture judgment exercised with AI assistance,
against SC-5: "a working core application with clean code is preferred over
ambitious but incomplete features." Several of these questions have a
maximum-safety answer that reads worse than the proportionate one, because
disproportion is itself a judgment failure. Where that is the case it is said
so, with the reasoning, so the record shows a decision rather than a reflex.

---

## 1. History rewrite for the tax identifier: NO

**Decision: do not rewrite history. Scrub forward, and record the decision.**

What the datum is: a Mexican RFC business tax registration number, printed on
the back of every bottle of a retail product sold publicly. It is not a
credential, not a secret, not a personal identifier, and not an applicant's
private filing data. That is a different class of thing from the signature
image on page 2 of the filing, which must never be committed and has not been.

What the rewrite would cost: a force-push of `main` and `develop`, re-creating
a published `v1.2.0` tag on a different commit, a GitHub support request, and
every commit hash in the CHANGELOG, the ADRs and eighteen merged pull request
bodies pointing at objects that no longer exist. A panel following a link from
the CHANGELOG to a dead commit is a worse outcome than the datum itself.

So: remove it from the tree, the fixtures, the tests and the current
documentation, and add a short entry to `docs/OPEN_QUESTIONS.md` or a decision
note recording that history was not rewritten, what the datum is, why the
exposure was judged low, and what would have changed the answer. **What would
have changed it:** a permit number tied to a named individual, a contact's
details, a signature, or anything that is not already printed on a public
retail package. State that line explicitly; it is the reusable part.

The review's finding stands as accepted with a recorded rationale, which is a
stronger artifact than a silently rewritten history.

## 2. The alcohol content false pass: DROP IT ENTIRELY

**Decision: remove `alcohol_content` from `RESCUED_FIELDS`. Do not build the
marker-restricted rescue.**

The tool exists to check five things. A false pass on one of them is the worst
defect class this application can have, and the rescue was a convenience.
Dropping it is small, provable and testable in one commit; the
marker-restricted version reintroduces the ABV-marker logic that already exists
from the Session 8 fix, in a second place, which is the duplication SC-5
penalises.

Add the reproduction as a regression test. Amend ADR 0015 to record that
decision 5 narrowed and why. If the "found in small print" benefit is wanted
later, it is an open question, not a v1.2.1 change.

## 3. Release shape: TWO RELEASES, as proposed

**Decision: hotfix v1.2.1 from `main`, then v1.3.0 on `develop`.**

This is the single clearest demonstration of engineering judgment in the whole
plan, and collapsing it into one release throws that away to save a day. It
shows severity triage, it exercises the documented Git Flow hotfix path a
second time (v1.0.1 was the first), and it puts the things a panel would trip
over into main quickly while the larger work proceeds on its own cadence.

Condition: the hotfix stays small. Findings 1, 3, 5, 14, 15 and the tree half
of 2 qualify. Nothing else joins it. If the hotfix grows past a day of work,
that is the signal it has stopped being a hotfix.

## 4. NFR-6 wording: REWORD, DO NOT RE-PLUMB

**Decision: correct the claim to be about retention. Do not switch Tesseract
to stdin.**

The promise printed on the screen is about retention, and retention is what an
agent cares about and what the system actually guarantees. "Nothing touches
disk" was the wrong claim to have made; the fix is to make the claim true, not
to contort the implementation until a poorly chosen sentence becomes true.

New wording in that direction: nothing uploaded is kept; files exist only for
the moments the check takes and are gone when it returns; there is no
database, no bucket and no log of content. Then
`docs/06_SECURITY_AND_COMPLIANCE.md` says plainly where the bytes live during
processing, including that the OCR engine reads through a short-lived
temporary file that it deletes.

Replace `TestNothingIsPersisted` with a test that asserts what is true and is
capable of failing: after a request completes, no artefact of it survives in
the working directory or the temp directory, and no content appears in a log
line.

Against stdin: it drops a maintained dependency, hand-rolls a subprocess
wrapper covering OSD and TSV output, and adds code to own for a guarantee the
reworded claim already gives honestly. SC-5 rewards owning less code. Record it
in `docs/OPEN_QUESTIONS.md` as the stronger guarantee available if the
requirement ever hardens.

## 5. TLS: NO DOMAIN, NO CIDR. STATE THE LIMITATION

**Decision: the prototype stays on HTTP. Do not add a CIDR restriction.**

A CIDR restriction would actively break SC-4: the deliverable is a URL
reviewers can reach and test, and they will reach it from networks nobody can
enumerate in advance. Trading the assignment's stated deliverable for a partial
mitigation is the wrong trade.

Buying and validating a domain for a stack whose posture is deploy, demo,
destroy is scope creep on the week before submission.

What to do instead, and it is worth doing properly because it is an
architecture answer rather than an omission: record in `docs/06` and the scope
document that the prototype is served over HTTP; that no credentials, no
session and no personal data cross the wire, because there is no
authentication and nothing is stored; and exactly what a real deployment would
add, which is an ACM certificate, an HTTPS listener on 443, a redirect on 80,
and the security group change to match. Name it as roughly one Terraform block
and say so. A reviewer reading "here is the gap, here is its size, here is why
it was not closed for a demo stack" reads competence; a reviewer finding an
unexplained `http://` reads an oversight.

## 6. OIDC: SCOPE BY BRANCH, NOT BY ENVIRONMENT

**This was checked rather than assumed.** The `production` environment on
this repository, as configured today: **Deployment branches and tags is "No
restriction". No protection rules. No environment secrets. No environment
variables.** Required reviewers are not available on a private repository at
this plan.

So the environment provides no gate at all, and an OIDC trust condition of the
`environment:production` shape would be security theatre: any branch can
deploy to an unprotected environment, so the condition would constrain
nothing.

**Decision: scope the trust policy by repository and ref.** Restrict the
subject to this repository and to the refs that are actually allowed to
deploy, which are `refs/heads/develop` and `refs/heads/main` plus the tag refs
the release trigger uses. Then say in `docs/06` that the environment carries
no protection rules today, that this is why the ref condition is the control,
and what would change if a deployment-branch policy were added later.
Recording the reason the other shape was rejected is worth more than the shape
itself.

## 7. The two PDFs: CONFIRMED OUT, AND YES, TRACK BOTH

**Confirmed.** Neither document enters the repository, a fixture, a log, an
issue body, a pull request body or a commit message, in whole or in part. They
are a local gate the author runs, and only measurements leave them: numbers,
timings, outcome names, and the metadata fields. The 3-page filing carries a
signature image on page 2; the printout carries a full applicant record.
Anyone repeating the gate uses their own copy.

The gate itself, recorded the way section 9 records measurements: the filing
must return five passes at about 4.8 s with `overrode_osd: true`; the printout
must read brand, class and item 5, and its alcohol content row must say not
found and never match.

**Yes, file both as tracked issues now**, before the release rather than after.

- **The artwork floor rejects real Registry artwork wholesale.** Seven embedded
  images, the largest at 1442 by 433, all rejected: the largest on aspect
  ratio, the rest on the short edge. Submitted alone the document returns
  `no_label_to_check`. This is the highest-value finding the secondary test
  produced, because the review had no real example of it and now there is one.
  It is also a design question, not just a threshold: the floor was set to
  exclude a signature, and it is excluding label artwork with the same rule.
- **The fanciful-name capture over-runs**, `_VALUE_LOOKAHEAD` swallowing a line
  belonging to the next item.

A known, tracked, unfixed defect with a reproduction is a strength in an
assessment. An unknown one is the thing that gets found by the panel.

**And a third, which the secondary test surfaced and which matters more than
it looks:** the item 5 margin came out at **12.1 points against a 12.0
floor**, on the very document the margin was derived from, while the code
comments describe a 22 point separation. That is a threshold sitting on a
knife edge with a comment that misdescribes it. One render-scale change flips a
correct reading to "not determined". Track it, fix the comment in the hotfix
if it is a one-line change, and take the measurement across both documents at
three render scales in v1.3.0 before moving the number.

## 8. Real brand name in historical prose: LEAVE THE RECORD, SCRUB THE FIXTURES

**Decision: change fixtures, tests and current documentation. Do not rewrite
CHANGELOG entries or ADR context.**

The line, and it is the reusable principle: **a record describes what
happened; a fixture asserts what should happen.** Rewriting a CHANGELOG so it
no longer says what the change was actually about is falsifying the record to
remove a brand name that is printed on a retail bottle. That is a worse act
than the exposure it prevents, and a panel that notices will read it as
tidying rather than judgment.

Fixtures and tests are different: a test asserting a real company's brand name
has real data as its expected value, which is a test-data defect independent
of sensitivity. Those become invented values, per finding 2's tree half.

This is consistent with decision 1. The tax identifier is not rewritten out of
history either; it is removed from the live surfaces going forward and the
decision is recorded.

---

## What this leaves for the hotfix, in order

1. Finding 1, alcohol content out of `RESCUED_FIELDS`, with the regression test
   and the ADR 0015 amendment.
2. Finding 3, version derived from one source, the CI step that fails on
   disagreement, CHANGELOG sections dated, bump to 1.2.1. This also closes the
   known `/api/health` reporting 1.1.0 on a v1.2.0 tag.
3. Finding 2, tree half: invented values in `ColourLabelSpec`, the two backend
   tests, the three frontend tests and the prose the review lists.
   Measurements unchanged.
4. Finding 5, ADR 0003 amended to "designed, not built", README and NFR-3
   reworded, the three Bedrock settings deleted, `external_call_made` made an
   honest constant with a comment.
5. Findings 14 and 15, the stale infrastructure openings, the lock-file
   paragraph, the `--strict` claim, the counts, and the small test that parses
   the matrix summary against the headings.
6. The item 5 comment corrected to the measured 12.1, if it is a one-line
   change.

Then the gate in decision 7, then tag v1.2.1.

Issues filed for decision 7: #121 (the artwork floor), #122 (the fanciful-name
over-run), #123 (the item 5 margin). The v1.3.0 work (decisions 4, 5 and 6,
and the remaining review findings) is tracked in #103 to #119.
