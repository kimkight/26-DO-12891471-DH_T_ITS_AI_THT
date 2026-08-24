# Sample labels and ground truth

This directory holds the labeled sample set used by the accuracy tests
described in [docs/07_TEST_STRATEGY.md](../docs/07_TEST_STRATEGY.md).

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
| `specs.py` | The twelve label specifications and the application data submitted against each | Yes |
| `generate_samples.py` | Renders the images and writes both CSVs | Yes |
| `warning_text.py` | The 27 CFR 16.21 statement, kept separate from the application's copy | Yes |
| `images/` | Rendered label artwork used as test input | No, git-ignored; see below |
| `expected.csv` | Ground truth: one row per image | Yes |
| `applications/applications.csv` | The application side of each case, in the A-14 column names | Yes |

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

## Batch application data CSV

`applications/` holds the comparison side of a test case. For batch submissions
(FR-8), application data is one CSV keyed by image filename, per
[ADR 0006](../docs/adr/0006-batch-execution-model.md). The contract:

| Column | Meaning |
| --- | --- |
| `filename` | Must match the filename of one submitted image part |
| `brand_name` | Application brand name, compared per FR-4 |
| `class_type` | Application class or type designation |
| `alcohol_content` | Application ABV, compared per FR-7 and A-12 |
| `net_contents` | Application net contents, compared per FR-7 and A-13 |
| `beverage_type` | Distilled spirits, wine, or malt beverage |

Example:

```csv
filename,brand_name,class_type,alcohol_content,net_contents,beverage_type
stones-throw-bourbon.png,Stone's Throw,Kentucky Straight Bourbon Whiskey,45%,750 mL,distilled spirits
```

**Two files, two purposes.** `expected.csv` is ground truth: what the tool
should extract from the artwork, used to score accuracy. The batch CSV is
input: what the applicant claims, which the tool compares the artwork against.
They overlap in columns and must not be conflated. `expected.csv` keys on
`image_filename`; the batch CSV keys on `filename`, matching the API contract.

This format is assumed rather than stated by any source, and is recorded as A-14
in [docs/ASSUMPTIONS.md](../docs/ASSUMPTIONS.md).

## Why images are git-ignored

`samples/images/` is listed in `.gitignore`. Label artwork can carry third-party
trade dress, and the assignment does not grant rights to redistribute real
label images. Contributors generate or source their own set locally.

The assignment states: "We encourage you to create or source additional test
labels; AI image generation tools work well for this."
[Source: Technical Requirements, Sample Label section]

## Cases the set covers

Derived from the interviews, these are the cases the accuracy and UAT tiers
exercise. See `docs/07_TEST_STRATEGY.md` for the assertions. Every case below is
present in `specs.py`. Case 7, batch submission, is exercised by
`backend/tests/test_batch.py`, which submits the whole set through
`POST /api/verify-batch` and asserts that every label returns a line; it needs
no spec of its own because a batch is the existing twelve labels sent together.

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
