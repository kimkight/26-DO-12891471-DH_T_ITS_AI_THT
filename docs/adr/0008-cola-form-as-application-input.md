# ADR 0008: Accept the COLA application document as an input, parsed locally

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-27 |
| Author | Kimberly D. Kight |
| Decision reference | Adds FR-11; implements US-23; records the boundary of OOS-1; supersedes nothing |

## Context

The question this answers was the author's, put plainly while using the
deployed prototype: **why do I have to enter in all this information?**

The five values the single-label form asks an agent to type in are brand name,
class or type designation, alcohol content, net contents and beverage type.
Those are values the applicant already submitted to TTB. They are on the label
application, TTB Form 5100.31, "Application for and Certification/Exemption of
Label/Bottle Approval", which is the COLA application filed through COLAs
Online; an approved application is also printable from the TTB Public COLA
Registry as a detail page carrying the same data.

Assumption A-8 records why the values are typed today: "There is no COLA
integration, so nothing can fetch application data automatically." That
inference is correct about fetching and wrong about typing. Nothing about the
absence of an integration says the agent has to retype a document they are
holding.

### The scope line, stated before anything is built on it

OOS-1 excludes COLA system integration. In Marcus Williams's words: "We're not
looking to integrate with COLA directly; that's a whole different beast with its
own authorization requirements." [Source: Marcus Williams interview] That
exclusion is not narrowed here. It means, and continues to mean:

- no calls to any COLA or COLAs Online API,
- no COLAs Online authorization, credentials, accounts or sessions,
- no lookups against the Public COLA Registry from the application, by API or by
  scraping.

**Accepting an uploaded copy of a completed form is document parsing, not
system integration.** The distinction is not a wording preference; it is what
Marcus's objection is actually about. What he names as the "whole different
beast" is the authorization requirement, and an uploaded file has none: the
agent already has the document, the tool never contacts TTB, and no credential
exists to manage. NFR-3 holds unchanged, because the default path still makes no
outbound call. NFR-6 holds unchanged, because the document is read in memory and
released with the request, exactly as a label photograph is.

If a future version were to look an application up rather than be handed one,
that would be the excluded thing, and it would need Marcus's decision rather
than this ADR.

### What the form actually contains

The blank form was downloaded once during development, from
`https://www.ttb.gov/system/files/images/pdfs/forms/f510031.pdf`, and its items
were read off the file rather than recalled. **Edition: TTB F 5100.31 (04/2023),
OMB No. 1513-0020; the form states "PREVIOUS EDITIONS ARE OBSOLETE".** Nothing
is fetched at runtime.

The result is not the tidy one this feature was hoped to have. Of the five
values the tool compares, **two are items on the form and three are not**:

| Value the tool compares | On TTB F 5100.31 (04/2023)? |
| --- | --- |
| Brand name | Yes, item 6, "BRAND NAME (Required)" |
| Beverage type | Yes, item 5, "TYPE OF PRODUCT (Required)", three checkboxes: WINE, DISTILLED SPIRITS, MALT BEVERAGES |
| Class or type designation | **No item.** It is on the labels affixed to the application |
| Alcohol content | **No item.** It is on the labels affixed to the application |
| Net contents | **Item 15 only**, and only when it is blown, branded or embossed on the container **and** does not appear on the labels |

The fanciful name is item 7, "FANCIFUL NAME (If any)". It is read and reported
because the document states it, and it is not compared: no source states a rule
that reads it.

A Public COLA Registry detail page is the other half of the answer. It does
carry a class or type designation, and it carries the numeric class/type code
alongside the description. The full field map is recorded as assumption A-17.

## Decision

**Accept an uploaded COLA document, PDF or image, as an alternative to typing
the application values, and extract them locally.**

### Where the values are read from, in order

A COLA document reaches an agent in one of three shapes, and each keeps its
values somewhere different. All three are handled, in this order:

1. **Form fields.** An applicant's filled-in copy of the downloadable PDF keeps
   its values in AcroForm fields. They are not in the page's text layer at all,
   so reading the page finds the blank template's captions and nothing else.
   This is also the only place a ticked checkbox can be read, which is what
   makes item 5 legible at all.
2. **Text layer.** COLAs Online output and a Registry printout are digitally
   generated, so the characters are in the file. Extraction is deterministic:
   no recognition step, no confidence figure, no misread.
3. **OCR.** A scan or a photograph of a printed form carries pixels only. Its
   pages are rendered and read through exactly the Tesseract pipeline label
   artwork goes through, and it inherits that pipeline's accuracy and its
   failure modes.

The first two are tried on every PDF. OCR runs only when neither produced a
single mapped value, because reading pages costs about what reading a label
photograph costs and there is nothing to gain by paying it for a document that
has already answered. `TTB_MAX_DOCUMENT_PAGES` bounds it, defaulting to 3.

The requirement as written asks for two paths, embedded text and an OCR
fallback. Three are implemented because the real form has three shapes, and
reading a filled-in fillable PDF through its text layer alone would return the
blank template. The addition is an elaboration of "embedded first, OCR
fallback", not a departure from it.

### What a ticked box can and cannot say

Item 5 is three checkboxes. A document's text layer prints the caption of an
unticked box exactly as it prints the caption of a ticked one, so a form whose
text names all three has said nothing about which was chosen. The beverage type
is therefore read from a form field where one exists, and otherwise only where
the document names exactly one of the three product types and no other. Anything
else is reported as not found and the agent chooses it.

Reading an "X" beside one of three boxes out of a scan was rejected. It is a
guess of exactly the kind FR-1 forbids, on a value the tool would then present
as having come off the application.

**Amended 2026-08-31 by [ADR 0016](0016-product-type-from-the-page.md): the tick
is readable, from the page rather than from the text.** Both paragraphs above are
still true about a *text layer*, and the conclusion drawn from them was too
narrow. The tool renders the document's pages already, and on the author's own
filing the ticked box is 22 luminance points darker than the two empty ones,
which the two empty ones are not from each other (they differ by 1.9). That is a
measurement rather than a guess, and it is not the "X" this ADR rejected reading:
nothing is recognized, three regions are compared, and the darkest is reported
only when it stands clear of the other two by a defended margin. Where it does
not, the answer is still not found and the agent still chooses.

What that changes here: the beverage type now has a third source, the form's own
check boxes, ranked below an AcroForm field and above the "names exactly one
type" inference this ADR settled for. What it does not change: the beverage type
is still never compared against the label, and the label artwork still cannot
supply it, because a label does not print a form answer.

### Precedence: a typed value always wins

Any explicitly typed field overrides the parsed value for that field, and the
response says which of the two supplied each value: `typed`, `parsed_from_form`,
`parsed_from_artwork`, `read_from_tick`, or `absent`. An agent who corrects a
field has read the document and disagreed
with what was read off it, and the tool defers to the agent everywhere else it
makes a judgement (FR-3, OOS-8). A blank field is not a correction, so the
parsed value stands.

### Parsed values are surfaced for confirmation, never silently trusted

The response carries the parsed application data as a distinct block, separate
from the comparison, and the interface writes it into the same editable fields
an agent would otherwise have typed into, each marked "Read from the application
form. Change it if it is wrong." The check runs on what is in the fields when
the button is pressed.

This is FR-3's philosophy applied one step earlier. A parsed value is a reading
of a document, not a fact about an application. The tool reads; the agent
judges.

### One route exists for that, and it is here rather than hidden

`POST /api/verify` accepts an optional `application_document` part, which is
what the requirement specifies, and applies the precedence rule to it.

A second route, `POST /api/read-application`, parses a document and compares
nothing. It exists because of what the interface has to do, not to give the API
a second way in: the parsed values have to reach the agent as editable fields
**before** a verification runs. Reaching that through `POST /api/verify` would
mean submitting the label photographs and running OCR over them once to read the
application and again to run the check the agent then asked for.

### The batch path is unchanged this session

The batch contract stays the CSV keyed by image filename (A-14). Per-row COLA
documents are a possible future extension and are **not built**. Nothing in the
batch path reads a COLA document.

> **Superseded on 2026-08-28 by
> [ADR 0009](0009-batch-cola-documents.md).** The possible future extension is
> the next session's work: a batch is label images plus one COLA document per
> label, paired by filename stem, read by this ADR's parser, and A-14's CSV is
> gone. Nothing else in this ADR changed.

## Alternatives considered

**COLA Registry API or scraping.** Rejected: it is precisely OOS-1, and it would
break NFR-3, which requires the default path to make no outbound call, on the
firewall Marcus Williams describes. It is also the option that needs the
authorization he named as the reason for the exclusion.

**Image stitching of form pages into one image before OCR.** Rejected for the
same reason ADR 0007 rejected stitching label photographs: it needs feature
matching on pages that do not overlap, and its failure mode is silent distortion
that reads as altered content. Pages are read independently and their fields
merged instead.

**Reading only the text layer, with no form-field reader.** Rejected on
evidence: the downloaded form is a fillable PDF whose 74 fields hold the
applicant's values, and a filled copy's text layer carries only the blank
template. This option would have returned "nothing found" for the single most
deterministic document shape there is.

**PyMuPDF for parsing and rendering.** Rejected on licence. It is AGPL, which is
not a licence to hand a federal agency without a conversation. `pypdfium2` does
the same three jobs under BSD-3-Clause and Apache-2.0, and carries PDFium as a
wheel, so nothing further has to be installed in the image.

**Asking the agent to type less by inferring values from the label itself.**
Rejected: that is the comparison, and using the label to supply the application
side would compare the label against itself.

## Consequences

**What improves.** The author's question is answered: an agent holding the
application does not retype it. Two of the five values, plus the fanciful name,
come off the form directly; a Registry printout supplies all five.

**What does not.** Three of the five values are not on the form, so an agent
working from the paper form still types the class or type designation and the
alcohol content, and usually the net contents. The tool says so, per value,
rather than reporting a bare "not found" that invites an agent to go looking for
a box that does not exist.

**What is now larger.** The single-label request may carry a fourth upload, so
the Content-Length guard admits 40 MB on the defaults rather than 30 MB. Every
individual file is still checked exactly against `TTB_MAX_UPLOAD_BYTES` after
parsing.

**A new dependency ships in the image.** `pypdfium2`, with PDFium behind it.
Both lock files are regenerated in the same change and both are audited in CI.

**What is not verified.** The parser has been exercised against synthetic
documents generated at test time and against the item map read off the blank
form. It has not been run against a real filed application or a real Registry
printout, because the no-personal-data rule forbids committing one and none was
available to the author. That is recorded as OQ-22 rather than glossed.
