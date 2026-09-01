# ADR 0017: The label artwork is read once, at check time, and never cached

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-09-01 |
| Author | Kimberly D. Kight |
| Decision reference | Narrows [ADR 0010](0010-embedded-label-artwork.md), which put the artwork into the application side; keeps [ADR 0011](0011-one-upload.md)'s read-once rule and extends it across the two requests one submission makes; NFR-1, NFR-6 |

## Context

A COLA document submitted alone costs an agent two requests, and until this
decision both of them read the same pictures.

Measured by the author at the deployed URL on 2026-09-01, with her own mezcal
filing, 382 KB:

| request | when it runs | measured |
| --- | --- | --- |
| `POST /api/classify` | the moment she picks the file | 5492 ms, 5410 ms |
| `POST /api/verify` | when she selects **Check this label** | 5331 ms to 5498 ms |

About eleven seconds of waiting for one document. The two requests are not doing
different work. `/api/classify` returned `artwork_images_read: 1`, which is the
whole of the cost in it: it ran the full artwork pass so that the alcohol
content and the net contents would appear in the five boxes, because assumption
A-17 says the form itself carries neither. `/api/verify` then read the same
picture again, because ADR 0010 makes that picture the label side when the agent
uploaded no photograph.

The document's own text layer takes 277 ms to read (`document_pdfium_ms`). Every
other millisecond in the prefill request was Tesseract.

## Decision

**`POST /api/classify` reads the document's text layer and stops.** It reports
what the text layer said, counts the pictures it found without reading them, and
says which of the two readings it did in `artwork_read`. The five boxes fill as
fast as the file uploads.

**The artwork is read once, at check time.** `POST /api/verify` already reads it,
because the check needs it for the label side. What it yields fills alcohol
content and net contents in the result, where an agent reads them next to the
outcome that used them rather than in a box they were asked to confirm before
anything had been checked.

**A field the artwork is about to supply is not a gap.** The interface treats a
gap as the only work left on the screen: the box opens, focus moves into it and
a live region says the value was not found. Saying that about a value the next
click reads off the artwork would be the tool asking an agent to do work it is
one second from doing itself. `artwork_read: false` plus a picture count is what
lets the interface tell the two apart; `artwork_images_read: 0` alone cannot,
because it is also what a document with unreadable pictures returns.

**`POST /api/read-application` still reads everything.** It is the FR-11 route
for a caller that wants the parsed values without verifying, and there is no
second request behind it to do the reading. Only the prefill pass changes.

## Not a cache. Not ever

The obvious alternative is to read the artwork in the prefill pass and keep the
result for the check a moment later. It is refused, and not on grounds of taste.

NFR-6 is an acceptance criterion of this system: nothing uploaded is persisted,
and no file content or extracted value reaches a log. It is also a promise
printed on every screen of the interface, above the masthead, on every view,
never dismissible:

> Prototype built for an employment assessment. Not an official TTB or Treasury
> system. Nothing you upload is stored.

A server-side cache of parsed documents is a store of uploaded content, whatever
its eviction policy and whatever it is called. It would hold label artwork and
the values read off it, keyed by something derived from an applicant's file,
across requests and therefore across agents. That contradicts the criterion and
it makes the banner false. The banner is the thing that makes this prototype
honest about what it is; a feature that costs half a second and makes it a lie
is not a trade this project makes.

Recorded here rather than left to be rediscovered: **do not solve the second
read with a cache.** The second read is gone because there is no second read,
not because its result was kept.

## What this costs

The alcohol content and the net contents are no longer in the five boxes before
the check runs. On a document-only submission they were never confirmable
anyway: they came off the artwork, and a value read off the artwork is compared
against that same artwork, which is why [ADR 0013](0013-artwork-derived-values.md)
refuses to call the result a match. Moving them to the result moves them to the
place where what they establish is stated honestly.

An agent who wants them before the check has the same route they always had:
type them, and FR-11's precedence makes the typed value win.

## Consequences

**What gets better.** The prefill request goes from about 5.4 s to about the
time the file takes to upload. The total an agent waits for one document falls
by roughly the whole of one Tesseract pass over the artwork, and the check that
remains is the one that was always going to run.

**What gets worse.** Two boxes fill later than they used to. See above.

**What is not decided here.** Whether the 180-degree orientation check should
score its two candidates at a lower resolution. That is [OQ-27](../OPEN_QUESTIONS.md)
and it is measured there.
