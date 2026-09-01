# ADR 0015: The application declares the answer, so the label is searched for it

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-31 |
| Author | Kimberly D. Kight |
| Decision reference | Rewrites FR-1 through FR-4; leaves FR-5, FR-6, FR-7 and FR-14 unchanged; supersedes the type-size half of [ADR 0004](0004-fuzzy-matching-with-review-band.md)'s pipeline while keeping its thresholds |

## Context

The tool has always worked in two steps: **locate** a value on the label, then
**compare** it against what the application declared. Locating is a ranking over
candidates. Comparing is a similarity score over two strings. Everything the
author has reported against a deployed build has been a failure of the first
step, and none of it a failure of the second.

The author uploaded a real mezcal COLA document alone to the released v1.1.0
build on 2026-08-30. Everything upstream worked. The application side filled
correctly, `DEL MAGUEY` for the brand name and `MEZCAL FB` for the class or type,
both out of the document's own text layer. The embedded label artwork was found,
lifted out, turned the right way up and read. And then two of the four compared
rows came back as defects:

> Does not match. Brand name. On the label: **Not found on the label**. On the
> application: DEL MAGUEY.
>
> "It is located by type size, and on this label the largest text was not clear
> enough of the next largest for type size to identify it, so it is reported as
> not found rather than as a guess (FR-1)."

Measured against the segmented label text the released pipeline produced from
that same document:

| declared by the application | present in the label text | best fuzzy score |
| --- | --- | --- |
| `DEL MAGUEY` | **yes, exact** | 100.0 |
| `MEZCAL` | **yes, exact** | 100.0 |
| `42% ALC BY VOL` | **yes, exact** | 100.0 |
| `750 ML` | **yes, exact** | 100.0 |

Four of four declared values were on the label, exactly, in text the tool had
already read and was holding in memory. It reported two of them as not found.

This is the fourth session in a row to fix an extraction defect, and the list has
one shape:

| session | what was reported | what actually happened |
| --- | --- | --- |
| Session 16 | brand name read as the producer's tax identifier | the type-size ranking picked a vertical strip in the gutter |
| Session 17 | brand name and class or type not found | the ranking declined, because nothing on the sheet stands clear |
| every session | beverage type left blank | it cannot be extracted from a text layer at all |

The author's summary of what the tool is for: "basically the whole goal is to
match what's in the application to the picture of the label."

## Decision

**Invert the comparison. Do not extract a value and compare it; take the value
the application declares and search the label for it.**

The application states the answer. The question is therefore not "what is the
brand name on this label", which requires a heuristic and can be wrong or can
decline, but "does `DEL MAGUEY` appear on this label", which has a reliable
answer even when the reading is imperfect. A search for a known target degrades
gracefully where a ranking fails outright: a misread character costs a few points
of similarity, where a ranking that declines costs the whole field.

### 1. The search contract

For each application-side value, in `backend/app/search.py`:

1. **Both sides are normalized** by `app.compare.normalize_text`, which is FR-4
   unchanged: case folded, typographic apostrophes straightened, punctuation
   dropped, whitespace collapsed.
2. **The label text is searched as segmented units.** One unit per region of the
   sheet, where a region is the panel `app.ocr` cut and the Tesseract block
   inside it, with the lines joined in reading order. `app.ocr` already
   guarantees no line spans two regions ([ADR 0014](0014-colour-as-an-ocr-candidate.md)
   and the panel work of v1.1.0), so a unit is one piece of the layout and a hit
   inside it can be reported as a place. Joining the lines is what finds
   `STONE'S` above `THROW`.
3. **Exact containment on word boundaries scores 100.** Word boundaries are what
   stop `VIDA` being found inside `INDIVIDUAL`.
4. **Otherwise the best window is scored** with the same `fuzz.ratio` the text
   comparison already used, over runs of words the length of the declared value
   give or take one, the slack absorbing a space OCR invented or dropped.
   Scoring windows rather than whole units is what stops forty words of body copy
   diluting a real hit.
5. **The outcome comes from `app.compare.classify`**, which is A-4's thresholds
   unchanged: 95 and above is a match, 80 to 95 is needs human review, below 80
   is not found. **No new number is introduced.** A similarity between a declared
   value and a run of label text is the same kind of quantity FR-3 already
   classifies, and a second scale for it would leave two definitions of "close".

### 2. The row reports where it was found

The old row printed the extracted value. The new row prints the label's own
printing of the matched run, and the reason names the column and the block it was
found in. That is more useful than an extracted value and not less: an agent can
see that the brand was found on the front panel rather than in the small print,
and a value found in the wrong place looks different from a value read badly.

It also makes Dave Morrison's case read better than it did. `STONE'S THROW` on
the label against `Stone's Throw` on the form is found case-insensitively, and
the row shows the label's casing beside the application's, so the agent can see
that the difference is case without being told.

### 3. The limit is stated, on the screen and in the requirement

**A hit establishes that the declared value appears on the label. It does not
establish that it appears as the brand, in the required type size, or on the
required panel.** Type size and prominence are OOS-5 and are not checked by this
prototype at all; that has always been true and the old design's "the brand name
is the largest text" implied otherwise.

One sentence, once, above the rows:

> This shows the declared value appears on the label. It does not show it appears
> as the brand, in the required type size, or on the required panel (OOS-5).

This is a weaker claim than the old design pretended to make, and a far stronger
one than "not found" about a string the tool has read. A weaker claim stated
plainly is worth more than a stronger one nobody can check.

### 4. The class or type is searched for its description, not its code

The application states `MEZCAL FB`. `FB` is a registry code and no label prints
it. So a trailing code token, one to three upper-case letters or digits, comes off
before the search and the row says that it did. **The full value is searched for
first**, so a designation that genuinely ends in a short upper-case token is
found before anything is stripped, and stripping can never lose a match.

### 5. Two fields keep their numeric comparison, and the search feeds it

The brand name and the class or type designation were located by type size, and
the search decides them outright. The alcohol content and the net contents are
located by pattern, which is deterministic and which read both of them correctly
on the author's own document. Their comparison is FR-7's, and A-12 and A-13
attach rules to it that a similarity score cannot express:

- two values in different units are needs human review, with no conversion
  performed (A-13);
- an alcohol content that cannot be parsed as a number is needs human review
  (A-12);
- a range is reported as a range, permitted for wine under 27 CFR 4.36;
- proof is cross-checked against 27 CFR 5.65, on the label alone;
- a label that carries neither is a regulatory finding in its own right
  (FR-14, [ADR 0013](0013-artwork-derived-values.md)).

Replacing that with a similarity score would lose every one of those, and would
report "different units" as a flat mismatch. So the search does not replace their
comparison. **What it does is supply the label side when the pattern found
nothing and the declared value is on the label anyway**, at or above the match
threshold, after which every one of those rules runs exactly as it did. The
rescue never overrides a value the pattern did read: that value is the label's own
statement of the field, and replacing it with a run of text that merely resembles
the application would be the tool grading its own homework.

### 6. Extraction does not disappear

Where the application supplied no value there is nothing to search for, and the
existing extractor is the fallback, with its existing honest not-found behaviour
and its existing explanation of a type-size decline. The API response says which
path ran, because the reason line reads differently: a searched row names what was
searched for and where it was found, and an extracted row names the ranking.

### 7. FR-5 is untouched

The government warning already works this way. It is a search for a fixed
statutory string, it is exact rather than fuzzy by requirement, and it returns an
exact match on the author's own document. Nothing here changes it, it carries no
similarity score, and the near-miss routing of
[ADR 0012](0012-warning-near-miss.md) stands.

## Alternatives rejected

### Better type-size heuristics

**Rejected because the author's own label defeats them, and not narrowly.** The
largest upright text on that sheet is `Vida Clasico`, which is the *fanciful*
name, item 7 on the form. The brand name, item 6, is `DEL MAGUEY`, set smaller.
"The largest text is the brand name" is not merely inconclusive on that label; it
is **wrong** on it, and a rule tuned until it stopped declining would confidently
report the fanciful name as the brand. That is worse than the defect it replaced:
the current failure is visible and the tuned one would not be.

The measurements are in `app.parse._STANDOUT_RATIO`. On the twelve sample labels
the second candidate is 0.46 to 0.64 of the first; on the author's artwork it is
0.83. No threshold in that gap identifies the brand on her label, because the
thing it would identify is not the brand.

### A vision model

**Rejected, unchanged from SG-2 and [ADR 0003](0003-local-ocr-default-bedrock-optional.md).**
A multimodal model asked "what is the brand name on this label" would probably
answer `DEL MAGUEY`. It would also make an outbound call on the default path,
which NFR-3 forbids and which the FedRAMP portability argument of NFR-10 rests
on; it would produce an answer no agent can trace to a place on the sheet; and it
would be a second, unfalsifiable source of the exact failure mode this ADR
exists to remove, a confident wrong value. The optional Bedrock path stays
optional and off.

### Searching without word boundaries

**Rejected because it manufactures agreement.** A plain substring search finds
`VIDA` inside `INDIVIDUAL` and `ALC` inside `BALSAMIC`. The whole value of the
inversion is that a hit means something; a hit that fires on a fragment of an
unrelated word means nothing and is harder to spot than a miss.

### Making the search decide the numeric fields too

**Rejected because A-12 and A-13 say more than a score can.** See decision 5. The
author's evidence shows the pattern extractor read both of those fields correctly
on the document where the type-size ranking failed, so there is no defect to fix
there and a real loss of behaviour to pay for it.

## Consequences

**A row can now say "found, in column 0, block 2" instead of "not found".** On
the author's document all four compared fields match.

**The claim the tool makes is narrower and true.** It no longer implies that it
identified the brand name; it says the declared text is on the label, and says
where. FR-1's acceptance criteria are rewritten to that contract.

**A wrong declared value is still a defect.** The search reports the closest text
it found and its score, so an agent can judge the call rather than trust it
(FR-3). `backend/tests/test_verify_by_search.py` asserts that a declared value
absent from the label is still reported as not found, on a fixture where the label
is full of text.

**Type size is no longer load-bearing for a supplied value**, and the sample-label
accuracy figures `scripts/measure.py` reports change meaning accordingly: they now
measure the search, because the script hands it the same reading the API does.

**The residual risk is a declared value that appears on the label somewhere other
than where it is required.** A brand name printed only in the small print of the
back panel is found and reported as found. That risk is stated on the screen, it
is what OOS-5 already excluded, and the region reported on the row is what lets an
agent see it.
