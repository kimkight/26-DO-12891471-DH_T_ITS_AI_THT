# Sample labels and ground truth

This directory holds the labeled sample set used by the accuracy tests
described in [docs/07_TEST_STRATEGY.md](../docs/07_TEST_STRATEGY.md).
Everything in it is generated from a specification, and everything in it is
invented.

`samples/real/` is the one exception and is a different kind of thing: two real
filed COLAs, the documents every measurement in this repository was taken on,
committed unaltered as evidence a reviewer opens. Nothing automated reads them.
See [real/README.md](real/README.md) and
[ADR 0021](../docs/adr/0021-real-filings-as-evidence-not-fixtures.md).

## Current status

**The sample set exists.** Twelve synthetic labels are described in
`specs.py` and rendered by `generate_samples.py`. `scripts/measure.py` runs the
verification engine over them and reports per-field accuracy and latency.

Regenerate the images and both CSVs from the repository root:

```
python samples/generate_samples.py
```

| Path | Purpose | Committed |
| --- | --- | --- |
| `labelmaker.py` | Renders one label from a specification, with Pillow | Yes |
| `formmaker.py` | Writes a synthetic COLA application document from a specification: a PDF with a real text layer, a fillable PDF whose values live in AcroForm fields, and a PNG with no text layer at all (FR-11, ADR 0008) | Yes |
| `specs.py` | The twelve label specifications and the application data submitted against each | Yes |
| `generate_samples.py` | Renders the images, writes both CSVs, and writes one COLA document per label | Yes |
| `warning_text.py` | The 27 CFR 16.21 statement, kept separate from the application's copy | Yes |
| `images/` | Rendered label artwork used as test input | No, git-ignored; see below |
| `expected.csv` | Ground truth: one row per image | Yes |
| `applications/applications.csv` | The application side of each case. No longer an API input; see below | Yes |
| `applications/documents/*.pdf` | One synthetic Registry printout per label, named to pair with its image (ADR 0009) | No, git-ignored; regenerated like the artwork |
| `applications/filed/*.pdf` | The same printout with the label artwork affixed: a filed application, a complete batch row on its own (ADR 0020) | No, git-ignored; regenerated like the artwork |
| `real/` | Two real filed COLAs, the documents the tool was measured on. Evidence a person opens, read by nothing automated (ADR 0021) | Yes, deliberately; see `real/README.md` |

### COLA application documents

`formmaker.py` is the same idea as `labelmaker.py`, applied to the application
rather than to the label. It writes three shapes of one invented application so
that each of the parser's three ways in is exercised on a document it did not
also produce: a digitally generated PDF, a filled-in fillable PDF, and a
rasterized copy with no text layer.

Nothing it produces is committed, and nothing real is used as a fixture. A
filed TTB F 5100.31 carries a permit number, a signature and a named person on
every copy, and the test data policy in
[docs/07_TEST_STRATEGY.md](../docs/07_TEST_STRATEGY.md) section 8 keeps real
application data and personal data out of every fixture. Every value in
`formmaker.py` is invented, and the permit and serial numbers are deliberately
not in a format TTB issues.

The two real filings the tool was measured on are a different thing and live in
`samples/real/`: evidence a reviewer opens, read by nothing automated, committed
so that the measurements in the deployment notes can be repeated on the
documents that produced them
([ADR 0021](../docs/adr/0021-real-filings-as-evidence-not-fixtures.md)).
OQ-22, which recorded that the parser had never been run against a real
application, is closed by those measurements; what each document showed is in
[real/README.md](real/README.md). A test that wants to assert on something one
of them contains wants a synthetic fixture, written here, that reproduces it.

### `expected.csv` columns

| Column | Meaning |
| --- | --- |
| `image_filename` | The rendered file in `images/` |
| `brand_name` | The brand name as printed on the artwork |
| `class_type` | The class or type designation as printed |
| `alcohol_content` | The alcohol content as printed, including any proof statement |
| `net_contents` | The net contents as printed, empty where the label omits it |
| `government_warning_present` | Whether any warning statement appears at all |
| `government_warning` | The warning statement as printed, empty where absent |
| `notes` | What this sample is for, and which defect it carries |

The first six columns and `notes` are the set this file originally planned.
`government_warning` was added because a boolean cannot serve as ground truth
for FR-5: scoring a warning comparison needs the statement as printed, not just
whether one is present.

**`warning_text.py` deliberately duplicates the application's constant.** The
sample set is input to the application, so taking its ground truth from
`backend/app/warning.py` would copy any typo there onto the artwork and score it
as correct. Both copies are checked against `docs/03_REQUIREMENTS.md` section 1
by `backend/tests/test_samples.py`.

## The application side of a batch

`applications/` holds the comparison side of a test case, in two forms.

**`applications/documents/*.pdf` is the application side of a paired batch
row.** Per [ADR 0009](../docs/adr/0009-batch-cola-documents.md), files that
share a filename stem are one row: `01-spirits-clean.png` and
`01-spirits-clean.pdf` are one label. `generate_samples.py` writes one synthetic
Public COLA Registry printout per label, carrying that label's declared values.

**`applications/filed/*.pdf` is a batch row on its own.** The same printout with
the rendered label affixed as an embedded image, which is what an importer
actually files, and since [ADR 0020](../docs/adr/0020-batch-items-are-derived.md)
a complete row: the artwork inside it is the label side and no image of the
same name is needed. `scripts/measure.py --batch --filed` submits this set, and
section 9 of `docs/09_DEPLOYMENT.md` measures the batch path on it.

A Registry printout rather than a blank TTB F 5100.31, because the form has no
item for the class or type designation, the alcohol content or the net contents
(A-17). A batch of forms would leave four of five fields with nothing to compare
against, which would make the sample batch useless as a measurement.

The documents are git-ignored, for the reason the artwork is: they are
regenerated from a fixed specification rather than committed. Every value in
them is invented; see the COLA application documents section above.

**`applications/applications.csv` is no longer an input to any API.** It was the
batch contract under assumption A-14, which
[ADR 0009](../docs/adr/0009-batch-cola-documents.md) supersedes: no source ever
stated that format, and nothing an importer files with TTB produces such a file.
The file stays because it is the application side of the accuracy tier, which
runs the engine in process, and because it is what the documents above are
written from.

**Two files, two purposes.** `expected.csv` is ground truth: what the tool
should extract from the artwork, used to score accuracy. `applications.csv` is
the other side: what the applicant claims, which the tool compares the artwork
against. They overlap in columns and must not be conflated. `expected.csv` keys
on `image_filename`; `applications.csv` keys on `filename`.

## Why images are git-ignored

`samples/images/` is listed in `.gitignore`. Label artwork can carry third-party
trade dress, and the assignment does not grant rights to redistribute real
label images. Contributors generate or source their own set locally.

The two PDFs in `samples/real/` are the exception, and a deliberate one. They
carry two companies' real label artwork, exactly as TTB publishes it in the
Public COLA Registry, because they are the documents the tool was measured on
and nothing else lets a reviewer repeat the measurement. That is a decision
about evidence, recorded with its reasoning and the alternatives declined in
[ADR 0021](../docs/adr/0021-real-filings-as-evidence-not-fixtures.md), and it
does not change the rule for this directory: `samples/images/` stays
git-ignored, the contributor's own set stays local, and nothing sourced for
testing is committed.

The assignment states: "We encourage you to create or source additional test
labels; AI image generation tools work well for this."
[Source: Technical Requirements, Sample Label section]

## Cases the set covers

Derived from the interviews, these are the cases the accuracy and UAT tiers
exercise. See `docs/07_TEST_STRATEGY.md` for the assertions. Every case below is
present in `specs.py`. Case 7, batch submission, is exercised by
`backend/tests/test_batch.py`, which submits the whole set through
`POST /api/verify-batch`, each label paired with its own COLA document, and
asserts that every label returns a line; it needs no spec of its own because a
batch is the existing twelve labels sent together with their applications.

1. A clean, correct label matching its application data on every field.
2. A brand name differing only in letter case, for example `STONE'S THROW` on
   the label against `Stone's Throw` in the application.
   [Source: Dave Morrison interview]
3. A government warning rendered in title case (`Government Warning`) rather
   than upper case, which must be rejected. [Source: Jenny Park interview]
4. A government warning with altered wording, which must be rejected.
5. A label where alcohol content or net contents disagrees with the application.
6. An unreadable image, which must produce a clear message rather than a
   silent failure or a false match.
7. A batch of several labels submitted together. [Source: Sarah Chen interview]

Photographs taken at an angle, under poor lighting, or with glare are a stretch
goal rather than a committed case; see `docs/02_PROJECT_SCOPE.md`.
[Source: Jenny Park interview]
