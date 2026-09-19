# Real filed COLAs used to test this tool

Two genuine, publicly published TTB Certificate of Label Approval filings.
Every measurement in `docs/09_DEPLOYMENT.md`, in the CHANGELOG and in the
artwork work of v1.4.0 was taken on these two documents. They are committed
so that a reviewer can run the tool against exactly what it was tested on,
rather than against a synthetic stand-in.

## The two documents

| File | TTB ID | Product | Pages | Embedded pictures |
| --- | --- | --- | --- | --- |
| `22118001000389-del-maguey-vida-mezcal.pdf` | 22118001000389 | mezcal | 3 | 2 |
| `15309001000084-woodford-reserve-bourbon.pdf` | 15309001000084 | bourbon whiskey | 4 | 6 |

Both were produced by opening the record's printable version in TTB's Public
COLA Registry and saving it as a PDF:

    https://ttbonline.gov/colasonline/viewColaDetails.do?action=publicFormDisplay&ttbid=<TTB ID>

Anyone can re-pull either one from that URL. Nothing here was obtained
privately, and nothing here was altered.

## What each one exercises

**22118001000389, the mezcal.** The passing case. One label picture at
1750 x 1150, a clean five of five. Its alcohol statement reads in the
`ALC BY VOL` form and its net contents in `750 ML`. This is the document the
tool was originally built against, and section 1 of the deployment notes
records why that was a problem: it is a sample of one.

**15309001000084, the bourbon.** The document that found three defects. Its
artwork is split across five separate pictures on three pages, sized
1950 x 862, 1350 x 300, 1103 x 340, 1050 x 309 and 187 x 1697. The class or
type, the alcohol content and the net contents are all on one line of type
along the bottom of the 1950 x 862 painting; the 187 x 1697 strip carries
two script signatures, a logo and a placeholder serial number, and none of
the five values. Every one of the five is placed upright by the page
(ADR 0025). Between them they carry:

1. an alcohol statement in the slash form, which the matcher did not handle;
2. a government warning that reads at 86.8 confidence but is overprinted with
   printer registration marks, so a word for word comparison fails on a label
   a human would pass;
3. a net contents statement, `1L`, at the end of the same line as the
   alcohol statement, along the bottom edge of the 1950 x 862 painting,
   which no arm of the reader finds on the session container's Tesseract
   (OQ-39). Until 2026-09-08 this item said the label carried no net
   contents statement; the panel shows one, and it is the reader that does
   not find it.

The shape rules removed in #140 and the panel stopping rule in #141 were both
found on this document.

## What is in them, stated plainly

These are filed applications, so each carries a basic permit number, a
business telephone number, the printed name of the applicant's authorised
agent, and two signature images. All of it is published by TTB on a public
website and is reproduced here unaltered from that source. The label artwork
is the trade dress of the respective companies and appears here only as it
appears in the public registry, solely to make this evaluation reproducible.

## What reads these files

Nothing automated. No test loads them, CI does not touch them, and no
assertion depends on their contents. Asserting on them would put their text
into the test suite, which is the thing the test data policy is written to
avoid; the regression tests remain synthetic and live in `samples/`, and
these two sit here as evidence a person can open.

See `docs/07_TEST_STRATEGY.md` section 8 for the policy as it now stands,
[ADR 0021](../../docs/adr/0021-real-filings-as-evidence-not-fixtures.md) for
the decision that changed it and the alternatives declined, and OQ-22 in
`docs/OPEN_QUESTIONS.md` for what running the tool on these two documents
measured.
