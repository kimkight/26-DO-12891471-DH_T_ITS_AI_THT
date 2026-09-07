# ADR 0021: Real filings are committed as evidence, and fixtures stay synthetic

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-06 |
| Author | Kimberly D. Kight |
| Decision reference | Amends the test data policy in [07_TEST_STRATEGY.md](../07_TEST_STRATEGY.md) section 8 and the reasoning in `samples/README.md`; closes [OQ-22](../OPEN_QUESTIONS.md#oq-22) by measurement; leaves NFR-6 and [ADR 0017](0017-read-the-artwork-once.md) unchanged. The two files landed in #142; this record is why they are there |

## Context

**Every measurement this repository reports was taken on one of two real
documents.** The first is the mezcal filing, TTB ID 22118001000389, a
three-page printable record from TTB's Public COLA Registry with its label
artwork embedded on page 3. It is the document the tool was built against and
the one the NFR-1 figure for the application-document path was measured on
(README, Measured performance and accuracy; [09_DEPLOYMENT.md](../09_DEPLOYMENT.md)
section 9; traceability source row 31). The second is the bourbon filing, TTB
ID 15309001000084, four pages with its artwork split across five pictures on
three pages. It returned one of five on the deployed v1.4.0 because the
artwork floor's shape rules rejected five of its six pictures (source row 42,
#121, #140), two of five on v1.5.0 because a fixed read count left its fifth
panel unread (source row 43, #141), and, with every panel read, three
separate defects, recorded in `samples/real/README.md`: an alcohol statement
in the slash form the matcher did not handle, a government warning that reads
well but is overprinted with printer registration marks so that a word for
word comparison fails on a label a human would pass, and a net contents
statement genuinely absent from every panel, which is a finding about the
label as submitted and not about the reader.

**The policy as it stood forbade committing either.** Section 8 of the test
strategy said that no real filed application was committed and none had been
parsed, and that a real filing is evidence, not a fixture, and is committed
nowhere: "not to `tests/`, not to `docs/`, not as an encoded blob, and not in
a pull request description". `samples/README.md` repeated it, and recorded
OQ-22 as the consequence: the parser had never been run against a real
application. The reason behind the rule is sound and is kept: an assertion
against a real document copies that document's content into the test suite,
and a filed application carries an applicant's record and a person's
signature (NFR-6).

**The rule had produced a contradiction of its own.** The README's latency
table had reported the mezcal filing parsed and read correctly since
2026-08-30, while OQ-22 stayed open on the ground that nothing real had been
parsed. And by v1.5.0 the bourbon had found three defects, every number
about them in the deployment notes and the CHANGELOG was taken on it, and a
reviewer reading those numbers could not repeat one of them. The deployment
notes said so themselves: "Nothing about the document enters the repository;
the numbers do." A measurement whose input the reader cannot open is a claim.

**What the two documents are.** Both are public records. TTB publishes every
approved COLA in the Public COLA Registry, the printable version of a record
is one URL keyed by TTB ID, and anyone can pull either document from it. Both
files were saved from that page and are committed unaltered. Each carries a
basic permit number, the applicant's business name and address as shown on
its permit, a business telephone number, the printed name of the applicant's
authorised agent, a signature image, and the label artwork, which is the
trade dress of the company that filed it. Neither states an email address.

**Who can see the repository.** It is private to its reviewers. Committing
the files puts them in front of nobody who could not already pull them from
the registry. `(Assumption)` A reviewer's private use of a public registry
record, to reproduce a measurement taken on it, is within what TTB publishes
the record for. That is the author's reading and not a stakeholder statement;
the assignment's own line on label images is that contributors are encouraged
to "create or source additional test labels", which is about the fixture set
and grants nothing about redistribution either way.

## Decision

The two filings are committed to `samples/real/` as evidence, unaltered, with
their provenance recorded beside them, so that a reviewer can run the tool
against exactly the documents every measurement was taken on. Every fixture
stays synthetic and invented. Nothing automated reads `samples/real/`: no
test, no fixture loader, no CI step and no script. The values the two files
carry are repeated nowhere else in the repository. NFR-6 is unchanged, because
its promises are about the running system and this decision is about the
tree. The decision is revisited before any change to the repository's
visibility, not after.

Section 8 of the test strategy now states the rule in that form, keeps the
paragraphs it replaced, and says why the position changed.

## Alternatives considered

### A. Cite the documents by TTB ID and give the registry recipe, committing nothing

The status quo, made explicit. The README and the deployment notes would name
the two TTB IDs and the registry URL, and a reviewer would pull the records
themselves.

Rejected. What a reviewer pulls is the registry's rendering of the record on
the day they pull it, printed from their browser, and not the file that was
measured; whether the two differ was not measured, and the point of the
change was to remove the question. It also puts a live external system
between the reviewer and the measurement during a review window the author
does not control. And it leaves the repository unable to show the thing its
own numbers are about, which is the contradiction this record exists to end.

### B. Send the documents with the submission, outside the repository

The two files would travel beside the submission, and the repository would
stay as it was.

Rejected. A submission is a single transfer; the repository is the record, and
it is versioned. Documents sent beside it fall out of version control, are not
tied to the commit they were measured on, and cannot be found by a reader of
the repository later. It would also do nothing for the contradiction: the
documents would still exist and still be the thing measured on, only less
visibly.

### C. Build a synthetic fixture that reproduces the bourbon's three failure modes, and commit that instead

A generated document carrying a slash-form alcohol statement, a warning
overprinted with registration marks and no net contents on any panel, in the
suite, as a regression test.

Not an alternative, and worth doing anyway. A fixture that reproduces a defect
proves that a fix holds; it does not let a reviewer repeat the measurement,
because the measurement was not taken on it. The suite already carries the
bourbon-shaped fixture for the panels and the stopping rule
(`backend/tests/test_artwork_panels.py`, which holds the bourbon's measured
pixel dimensions and nothing else of it). A fixture for the three defects is
the next one to write, in a later session, and when it exists it is the thing
a test asserts on. That is the policy's own rule, applied: assert on the
synthetic reproduction, open the real document.

## Consequences

**Positive**

- A reviewer can reproduce every measurement in the repository on the
  documents that produced it, from the tree alone.
- The documents and the tree agree. Section 8, `samples/README.md`, the
  README status table and OQ-22 no longer describe a repository that does not
  exist.
- OQ-22 closes by measurement rather than by assertion, and the closure
  records something the question anticipated: the two printouts are the
  07/2012 and 06-2016 editions of TTB F 5100.31, neither the 04/2023 edition
  the item map was read off, and they number their items differently.

**Negative**

- The repository carries two businesses' permit records, an agent's printed
  name and two signature images. That is a real cost, and "public record"
  reduces it without removing it.
- The policy now has an exception a contributor has to understand. The old
  rule could be applied without thought; this one asks the contributor to
  know the difference between a fixture and evidence, and the section is
  written to make that difference hard to miss.
- The reasoning here does not extend mechanically to a third document. Each
  addition to `samples/real/` is a decision of this kind, recorded the same
  way, and not a habit.
- About 1.2 MB of binary content in history.

**Risks accepted**

- **A change of visibility.** If the repository is ever made public, the
  case above no longer holds, and removing the files from history is a
  rewrite rather than a deletion. So the decision is revisited before any
  such change, and that order is the mitigation.
- **Something automated starts reading them.** The policy names the rule, the
  evidence README names it, and the check is a search for `samples/real` in
  `backend/tests/`, `frontend/`, `scripts/` and `.github/`, which finds
  nothing today. A contributor who wants to assert on their contents is
  directed to write a synthetic fixture.
- **An objection from TTB or an applicant.** Considered unlikely for an
  unaltered public record used privately for its stated purpose, and not
  measured. If it comes, the files are removed and the measurements revert to
  citations by TTB ID, which is alternative A with its costs.

## References

- [07_TEST_STRATEGY.md](../07_TEST_STRATEGY.md) section 8, the policy as it
  now stands and as it stood.
- `samples/real/README.md`, the provenance of both documents and what each
  one exercises; `samples/README.md`, why the generated set stays synthetic.
- [OQ-22](../OPEN_QUESTIONS.md#oq-22), closed by this decision.
- [09_DEPLOYMENT.md](../09_DEPLOYMENT.md) section 9 and traceability source
  rows 31, 42 and 43, the measurements taken on the two documents.
- [ADR 0010](0010-embedded-label-artwork.md) as amended, the two defects the
  bourbon found in the artwork floor; [ADR 0017](0017-read-the-artwork-once.md),
  no cache, unchanged.
- [03_REQUIREMENTS.md](../03_REQUIREMENTS.md), NFR-6, unchanged.
- #121, #140, #141, #142.
