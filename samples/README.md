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
