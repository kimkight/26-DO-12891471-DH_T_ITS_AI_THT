# Sample labels and ground truth

This directory will hold the labeled sample set used by the accuracy tests
described in [docs/07_TEST_STRATEGY.md](../docs/07_TEST_STRATEGY.md).

## Current status

**No sample labels and no `expected.csv` exist yet.** Nothing in this directory
is wired into the test suite. The accuracy and performance test tiers are
blocked until the sample set is built.

## What will go here

| Path | Purpose |
| --- | --- |
| `images/` | Label artwork used as test input. Git-ignored; see below. |
| `expected.csv` | Ground truth: one row per image, one column per extracted field. |
| `applications/` | Matching application data used as the comparison side of a test case. |

`expected.csv` is the ground truth referenced by the accuracy tier. Its planned
columns are `image_filename`, `brand_name`, `class_type`, `alcohol_content`,
`net_contents`, `government_warning_present`, and `notes`.

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

## Cases the set must cover

Derived from the interviews, these are the cases the accuracy and UAT tiers
exercise. See `docs/07_TEST_STRATEGY.md` for the assertions.

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
