# Accessibility conformance report

**Product:** TTB Label Verifier (prototype)
**Author:** Kimberly D. Kight
**Date of this report:** 2026-09-02
**Version evaluated:** v1.3.0, on `develop`, built by `npm run build` and served
from `dist/`, which is the page an agent loads. The v1.2.0 code review
(`CODE_REVIEW_2026-09.md`, finding 7) found four rows of the previous edition
that the code contradicted and four tests behind them that could not fail;
those rows are corrected below and the tests were rewritten and each proved
able to fail (pull request B of v1.3.0 records the mutation used for each).

## 1. What is claimed

**Section 508 conformance, evaluated against WCAG 2.0 Level A and AA, and
verified to WCAG 2.1 Level AA.**

Section 508 of the Rehabilitation Act, as revised in 2017 (36 CFR Part 1194,
Appendix A), adopts WCAG 2.0 Levels A and AA as the standard for web content at
E205.4. That is the standard this report is written against.

NFR-5 in [03_REQUIREMENTS.md](03_REQUIREMENTS.md) targets WCAG 2.1 Level AA,
which is a superset: every WCAG 2.0 AA criterion is a WCAG 2.1 AA criterion, and
2.1 adds twelve more. The work of this report was therefore mostly verification
and documentation rather than remediation, and where a 2.1-only criterion is
recorded below it is marked as such: it is verified, and it is above what
Section 508 requires.

**This is a self-assessment by the author, not a third-party audit, and it is
not a VPAT.** It is written to the level of detail a reviewer for a federal role
would expect to be able to check, and its exceptions are listed in section 5
rather than omitted.

## 2. How it was tested

Five methods, and the fourth and fifth are the ones that matter for the
criteria a tool cannot evaluate.

| Method | What it covers | Where it lives |
| --- | --- | --- |
| **axe-core against the built page** | The subset of failures a rule engine can detect: missing labels, skipped heading levels, broken ARIA relationships, rendered contrast. Run on the landing page, the batch tab, the Help tab, the collapsed and open disclosure, a five-row result, an error notice, a document-only result, and a two-photograph result. | `frontend/tests/a11y.spec.ts` |
| **A computed contrast test over the palette** | Every colour token against every surface it is used on, computed from `index.css` rather than from a table copied out of it, with the outcome list read off the outcome definitions and the focus-ring token read off the rule for each ground. It checks pairs that no component happens to combine today, which is where a later change fails. | `frontend/src/__tests__/contrast.test.ts` |
| **A keyboard walk in a real browser** | Tab order, focus visibility computed from the rendered style, arrow-key navigation of the tab set, and operability by Space as well as Enter. | `frontend/tests/a11y.spec.ts` |
| **A manual criteria pass, automated where it could be** | Reflow at 320 pixels, text spacing overrides, 200 percent zoom, use of colour under a greyscale filter, name-role-value on every custom control, and status-message regions. axe reports these as "incomplete" or not at all. | `frontend/tests/a11y.spec.ts`, `test.describe('the criteria a tool reports as incomplete')` |
| **A criterion-by-criterion review by the author** | The rest: meaningful sequence, focus order, error identification and suggestion, labels and instructions, headings and labels, consistent identification. Recorded in section 4 with what was examined. | This document |

**Every automated check above runs in CI on every pull request**, in the
`frontend lint, test and build` job. A conformance claim that is not
regression-gated decays within a release.

## 3. Reading the results below

| Term | Meaning |
| --- | --- |
| **Supports** | The criterion is met throughout the product. |
| **Partially supports** | Some functionality does not meet the criterion. The exception is stated. |
| **Not applicable** | The product has no content the criterion governs. |

## 4. Criterion by criterion

### Principle 1: Perceivable

| Criterion | Level | Result | Evidence, and what was examined |
| --- | --- | --- | --- |
| 1.1.1 Non-text Content | A | Supports | The interface has no informational images. The outcome icons are decorative: each is `aria-hidden` and sits beside a word that says the same thing, so labelling both would make a screen reader say "match match". The file preview shows the agent's own uploaded artwork and carries its filename as a caption. axe's `image-alt` and `role-img-alt` rules pass on every page. |
| 1.2.x Time-based Media | A, AA | Not applicable | The product contains no audio, video, or prerecorded media of any kind. |
| 1.3.1 Info and Relationships | A | Supports | Every input has a `<label>` bound by `htmlFor`. The result rows are `<dl>` key-value pairs, not visually aligned `<div>`s. The warning difference uses `<del>` and `<ins>`, which mean exactly what is being shown. The tab set carries `role="tablist"`, `role="tab"` and `role="tabpanel"` with `aria-controls` and `aria-labelledby` in both directions. Heading levels are checked as a sequence on the Help tab rather than as a count. |
| 1.3.2 Meaningful Sequence | A | Supports | The DOM order is the reading order on every view: banner, masthead, tab strip, panel, footer, and within the single-label panel, upload then application values then submit then results. Nothing is positioned out of order by CSS; the layout is flex and grid over source order, with no `order` property. Two things are absolutely positioned: the skip link, which is first in the DOM as well as first in the tab order, and the `.visually-hidden` live regions, which is the standard off-screen pattern and carries no visible content, so the reading order is unaffected. |
| 1.3.3 Sensory Characteristics | A | Supports | No instruction refers to shape, size, or position. Controls are named in text ("Check this label", "Clear and start another label"), and the one reference to a control from prose names it by its label rather than by where it is. |
| 1.3.4 Orientation | AA (2.1) | Supports | Nothing restricts orientation. The layout is a single column below the breakpoint. |
| 1.3.5 Identify Input Purpose | AA (2.1) | Not applicable | No input collects information about the user. Every field describes a beverage label, not the person filling it in, so no `autocomplete` token applies. `autoComplete="off"` is set to stop a browser offering unrelated saved values. |
| 1.4.1 Use of Colour | A | Supports | Every outcome carries a word, a shape, and only then a colour. **This is the criterion the release made load-bearing**: FR-15 gives Contains the same green as Match because both are passes, so colour no longer separates them at all. Verified under an actual greyscale filter on two different results, asserting that every outcome on the page has a distinct word and a distinct SVG path. The warning difference marks its runs with the words "missing:" and "extra:" as well as with a tint. |
| 1.4.2 Audio Control | A | Not applicable | Nothing plays automatically. |
| 1.4.3 Contrast (Minimum) | AA | Supports | Computed from the tokens as rendered. Every foreground against every surface it is used on, every outcome colour against its own tint, and body text against every tinted card. Derived from the outcome list itself rather than from a list kept beside it, so an outcome added with an unchecked tone fails the test rather than shipping. axe checks the same thing again on the rendered page, where a stylesheet change would break it. |
| 1.4.4 Resize Text | AA | Supports | Verified at 200 percent, with a five-row result on the page and no horizontal scrolling. Nothing is sized in fixed pixels that carries text. |
| 1.4.5 Images of Text | AA | Supports | There are none. Every string on the page is text. |
| 1.4.10 Reflow | AA (2.1) | Supports | Verified at 320 by 256 pixels, which is 1280 by 1024 at 400 percent, on all three tabs and with a five-row result on the page. No horizontal scrolling on any of them. |
| 1.4.11 Non-text Contrast | AA (2.1) | Supports | The focus ring is checked at 3:1 against every ground it lands on, with the ring token for each ground read off the stylesheet's own rule rather than assumed: the navy ring on both surfaces, the pale navy pill track, the page shell and the prototype banner; the gold ring on the navy masthead, which is the only place the stylesheet switches to it. (Until v1.3.0 the stylesheet also drew the gold ring on the pale banner, where it computes to about 1.5:1, while the test checked the navy ring there; nothing in the banner is focusable, so no agent met it, and the rule and the test are both corrected.) The gold rules and edges are checked at 3:1 against every surface they sit on. The active pill's fill is about 1.2:1 against its track and is not relied on to carry the state: the weight change, the shadow and `aria-selected` do, and the test asserts those rather than the fill. |
| 1.4.12 Text Spacing | AA (2.1) | Supports | Verified with line height, letter spacing, word spacing and paragraph spacing all overridden to the values the criterion names. Nothing is clipped and nothing scrolls sideways. |
| 1.4.13 Content on Hover or Focus | AA (2.1) | Not applicable | Nothing appears on hover or on focus. There are no tooltips and no hover menus. |

### Principle 2: Operable

| Criterion | Level | Result | Evidence, and what was examined |
| --- | --- | --- | --- |
| 2.1.1 Keyboard | A | Supports | Every control is a real HTML control. The file picker is an `<input type="file">` with a `<label>` around it, visually hidden rather than `display: none` so it stays in the tab order and the accessibility tree; drag and drop is added on top and nothing depends on it. The reset is a `<button>`, verified operable by Space in a browser, which is what separates a button from a styled anchor. The tab strip is driven by arrow keys, Home and End. |
| 2.1.2 No Keyboard Trap | A | Supports | Nothing takes focus and holds it. There are no modals, no dialogs and no embedded content. The keyboard walk tabs from the top of the document to the end of the form without becoming stuck. |
| 2.1.4 Character Key Shortcuts | A (2.1) | Not applicable | There are no single-character shortcuts. |
| 2.2.1 Timing Adjustable | A | Supports | Nothing is timed. A batch stream can be stopped by the agent and has no timeout the agent must beat. |
| 2.2.2 Pause, Stop, Hide | A | Supports | The only movement is the three-dot pulse while a batch is reading. It stops for anyone who has asked for reduced motion, it is `aria-hidden`, and the live region beside it carries the same information as text. |
| 2.3.1 Three Flashes | A | Supports | Nothing flashes. |
| 2.4.1 Bypass Blocks | A | Supports | A skip link is the first thing in the tab order and jumps to `#main`. |
| 2.4.2 Page Titled | A | Supports | `TTB Label Verifier (prototype)`. The parenthetical is in the tab title as well as on the page, because a bookmarked tab is the one place the page's own banner cannot reach. |
| 2.4.3 Focus Order | A | Supports | Source order throughout. The one place focus is moved deliberately is where the criterion bites: **the reset control removes the element that had focus, which is itself**, so focus is moved to the file picker rather than dropped to `<body>`. Focus is also moved to the first unanswered field when a parsed document leaves a gap, which is announced. |
| 2.4.4 Link Purpose (In Context) | A | Supports | The only link on the page is the skip link, named by its own text. The Help tab's prose contains no links; the previous edition of this row said it did. |
| 2.4.5 Multiple Ways | AA | Not applicable | This is a single-page application with three panels and no set of pages to navigate between. |
| 2.4.6 Headings and Labels | AA | Supports | Every heading describes the section under it. The Help tab's headings are the questions an agent would ask, in their words. Every field label names the value rather than the box. |
| 2.4.7 Focus Visible | AA | Supports | A 3 pixel solid ring on every stop, verified by reading the computed style under real keyboard focus rather than by asserting the rule exists. The file picker's ring is carried by its wrapper through `:focus-within`, because the input itself is visually hidden. |
| 2.5.1 Pointer Gestures | A (2.1) | Supports | No gesture is required. Drag and drop is an addition to a file picker that works without it. |
| 2.5.2 Pointer Cancellation | A (2.1) | Supports | Every action fires on click, not on down-event. |
| 2.5.3 Label in Name | A (2.1) | Supports | Every control's accessible name contains its visible label; the names are the visible text in every case, with no `aria-label` overriding a visible string. |
| 2.5.4 Motion Actuation | A (2.1) | Not applicable | Nothing responds to device motion. |

### Principle 3: Understandable

| Criterion | Level | Result | Evidence, and what was examined |
| --- | --- | --- | --- |
| 3.1.1 Language of Page | A | Supports | `<html lang="en">`. |
| 3.1.2 Language of Parts | AA | Not applicable | The interface is entirely in English. Values read off an uploaded label are the applicant's own text and are reproduced verbatim; marking a language on them would be a guess about content the tool does not understand. |
| 3.2.1 On Focus | A | Supports | Focus changes nothing. |
| 3.2.2 On Input | A | Supports | Typing into a field changes only that field's own source mark. Choosing a file starts a read and announces it. Where the application the agent chose leaves a value unread, focus then moves to the box for that value (FR-13): that is a change of context, and the criterion is met the way it names, by advising the agent beforehand. The file picker's own hint says the cursor will move if the application leaves a value unread, before any file is chosen. A photograph on its own opens no box and moves focus nowhere (v1.3.0). The previous edition of this row called the focus move a change of content; it is not. |
| 3.2.3 Consistent Navigation | AA | Supports | The tab strip is in the same place with the same order on every view. |
| 3.2.4 Consistent Identification | AA | Supports | One word per outcome and one shape per outcome, asserted rather than intended: the contrast test fails if two outcomes share either. One label per value source. "Check this label" means the same thing everywhere it appears. |
| 3.3.1 Error Identification | A | Supports | Every failure is described in text, in the agent's terms, in a `role="alert"` region that interrupts because it replaces the thing they were waiting for. The API's own message is kept underneath as the detail, because it is the half that names the limit. |
| 3.3.2 Labels or Instructions | A | Supports | Every input has a label. The two that need a format have a hint bound by `aria-describedby`. The submit control says why it is inert when nothing is uploaded. |
| 3.3.3 Error Suggestion | A (AA) | Supports | Each message says what to do rather than only what went wrong: send a clearer image, send a smaller file, send at most three photographs, type the values instead. A field the document did not answer opens with a sentence saying to enter it or upload a clearer file. |
| 3.3.4 Error Prevention (Legal, Financial, Data) | AA | Not applicable | The product makes no transaction, stores nothing, and deletes nothing of the user's. Its output is a recommendation the agent acts on outside this tool. |

### Principle 4: Robust

| Criterion | Level | Result | Evidence, and what was examined |
| --- | --- | --- | --- |
| 4.1.1 Parsing | A | Supports | The markup is generated by React and validated by the TypeScript build. axe's duplicate-id rules pass on every page. Components that can render more than once (the drop zone, the upload panel) take their ids from `useId`; the application fields component renders once per page and names its inputs after the fields, statically, which the previous edition of this row overstated as `useId` throughout. (This criterion is removed in WCAG 2.2 and is recorded here because Section 508 adopts 2.0.) |
| 4.1.2 Name, Role, Value | A | Supports | Verified on the three controls that are built rather than borrowed. The pill control is a real tab set: `role="tablist"`, one `role="tab"` per segment, `aria-selected` on the current one, `tabIndex` of -1 on the rest, arrow-key navigation, and each panel associated with its tab. The disclosure is a `<button>` with `aria-expanded` and `aria-controls` over a panel hidden with `hidden`, so it leaves the tab order and the accessibility tree together. The outcome chips are text, not controls, and are asserted not to claim a button role. |
| 4.1.3 Status Messages | AA (2.1) | Supports | Five polite `role="status"` regions, each labelled apart so a screen reader says which one spoke: the uploads, the application values, the check result, the batch pairing and the batch progress. Each is always in the DOM rather than mounted with its text, because a live region added at the same moment as its content is not reliably announced; the batch pairing region was mounted with its text and unlabelled until v1.3.0, and the batch progress region was unlabelled, which the previous edition of this row, which counted four, could not see. The test now opens the batch tab and asserts all five by role, politeness and name, and that no two names are the same. The reset's announcement uses the check-result region, which is the one it emptied. |

## 5. Exceptions, and what is not covered

Three, stated plainly. A truthful report with exceptions is worth more to a
reviewer than a blanket claim.

### 5.1 No screen reader was used

**This is the largest gap in this report and it is a real one.**

No testing was performed with NVDA, JAWS, VoiceOver, Narrator, TalkBack, or any
other assistive technology. Everything in section 4 about what a screen reader
announces is inferred from the roles, names, states and live regions in the
markup, and verified by reading the accessibility tree that a browser builds
from them. That is not the same as hearing it.

What that does and does not leave open: a missing label, a wrong role, a broken
relationship or an unannounced status region would very likely have been caught
by the checks that were run, because each is a property of the markup. What
would not be caught is the shape of the experience: whether the announcements
are said in an order that makes sense, whether a five-row result is tolerable to
listen to, whether the live regions interrupt each other in practice, and
whether the words chosen are the right words when heard rather than read.

**Recommended before any use beyond this assessment:** a pass with NVDA on
Firefox and one with VoiceOver on Safari, on the single-label check end to end
including a failure and a reset.

### 5.2 Bold type on the government warning is not checked

27 CFR 16.22(a)(2) requires the "GOVERNMENT WARNING:" prefix to be in capitals
**and in bold**. This tool checks the capitals and does not check the typeface;
it is out of scope as OOS-4 and it is stated on the affected row rather than
omitted.

This is a product limitation and not an accessibility one, and it is listed here
because a reviewer reading a conformance report is entitled to know that the row
is telling them something it has not fully checked. Nothing about how that
limitation is *presented* is an accessibility exception: it is text, on the row,
in a labelled section.

### 5.3 What was evaluated, and what was not

This report covers the web interface as built and served from this application's
own container. It does not cover:

- **The API on its own.** `POST /api/verify` and the other routes return JSON.
  A caller with no interface reads the reason strings, which is why the API
  appends limits and notes to them that this interface strips and states once.
  There is no accessibility standard being claimed for a JSON body.
- **The CSV a batch downloads.** It is data for a spreadsheet, and its
  accessibility is a property of whatever opens it.
- **Any document an agent uploads.** A scanned COLA application is the
  applicant's file, not this product's content.
- **Windows High Contrast Mode and forced-colours modes.** Not tested. The
  interface's reliance on shape and text rather than colour should carry it, and
  "should" is not a measurement.

## 6. What would change this report

- A screen reader pass, which would move section 5.1 from an exception to
  evidence, or find something.
- Any new outcome, control, or colour token. The contrast test derives its list
  from the outcome definitions and will fail rather than pass silently, but the
  criterion review in section 4 is written by a person and has to be re-read.
- A change to the tab set, the disclosure, or the reset. Those three are the
  custom controls, and they are where name-role-value is either true or false.
- A new `role="status"` region, which the status-region test counts and
  names, so an unlabelled one fails the build.

## 7. Related documents

- [03_REQUIREMENTS.md](03_REQUIREMENTS.md), NFR-5, which states the target and
  now cites Section 508 explicitly.
- [TRACEABILITY_MATRIX.md](TRACEABILITY_MATRIX.md), which traces NFR-5 to its
  stories and its tests.
- [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md), OQ-7: whether Section 508 formally
  applies to a prototype of this kind, and whether the agency holds a standard
  beyond WCAG 2.1 AA, is still a question for the agency rather than one this
  report can answer. **The work was done as though it applies**, which is the
  only useful way to hold an open question of that shape.
