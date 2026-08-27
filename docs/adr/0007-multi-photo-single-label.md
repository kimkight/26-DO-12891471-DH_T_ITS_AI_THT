# ADR 0007: More than one photograph of one label

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-26 |
| Author | Kimberly D. Kight |
| Decision reference | Amends FR-1; implements US-22; works around SG-1 and the risk accepted in [ADR 0003](0003-local-ocr-default-bedrock-optional.md) |

## Context

The first photograph of a real bottle submitted to the deployed prototype
returned none of its five fields. Three causes were found by inspecting the
photograph. Two were fixed in the preprocessing path and are recorded as
assumption A-15: the photograph was taken sideways, and it carried its
orientation in an EXIF tag that OpenCV ignores on decode.

The third cause is geometry and cannot be fixed the same way. **A wine label
wraps a round bottle.** No single photograph shows the whole label flat: the
part of the label facing the camera is readable and the parts curving away
compress, distort and eventually disappear. It is the same problem whichever
way the bottle is turned, and it is the reason Jenny Park raised imperfect
images at all: "labels that are photographed at weird angles, or the lighting is
bad, or there's glare on the bottle... this is maybe out of scope for a
prototype." [Source: Jenny Park interview] It is recorded as SG-1, a stretch
goal, and as the risk ADR 0003 accepted when it chose local OCR: that Tesseract
reads real photographed artwork worse than a cloud service would.

The facts that constrain what can be done about it:

- **The required elements are not all on one face.** 27 CFR 16.21 requires the
  government warning "on the brand label or separate front label, or on a back
  or side label", so the regulation itself contemplates the warning being
  somewhere other than the front. A tool that can only see one face can be
  asked for a field that is physically not in the frame.
- **No source states how many photographs an agent would take**, or whether
  they take more than one today. Sarah Chen describes an agent who "pulls up an
  application, looks at the label artwork", singular. The cap chosen below is
  therefore marked as an assumption.
- **D-9 forbids persistence.** There is no place to accumulate photographs
  across requests, so more than one photograph means more than one part in one
  request.
- **NFR-1 sets about 5 seconds per label.** Reading three photographs is three
  reads, and orientation detection has already roughly doubled the cost of one
  (A-15). Three photographs is measurably slower than one and the figure has to
  be reported rather than assumed.
- **FR-8 already accepts many images in one request**, with per-row isolation
  and a file-count cap, so the shape of a multi-image submission is settled;
  what is new is that several images describe *one* label rather than several.

## Decision

**`POST /api/verify` accepts one to three `image` parts, all of the same label.
Each photograph is decoded, turned upright and read independently, and the
fields found across all of them are merged into one result.**

1. **Independent OCR per photograph.** Nothing is stitched. Each photograph goes
   through the same pipeline a single photograph goes through today, producing
   its own text, its own line geometry, and its own orientation record.
2. **A union of the extracted fields.** A field counts as found if any
   photograph shows it. The five field results, the warning detail and the
   comparison against application data are all as they are today: one label, one
   set of application values, one result.
3. **Where two photographs both show a field, the better reading wins, and each
   field is judged by the signal that located it.** Alcohol content and net
   contents are found by pattern, so the higher per-field OCR confidence wins.
   The brand name and the class or type designation are found by type size
   (`app/parse.py`), so type size decides between them as well: merging those
   two by confidence alone would let the small print on a photograph of the back
   of the bottle, read perfectly, outscore the brand name on a photograph of the
   front. Type size is comparable between photographs because every image is
   scaled to the same long edge before it is read. An exact tie goes to the
   earlier photograph, so the result does not depend on iteration order.
4. **The warning is chosen by the length of the located statement**, ties going
   to confidence and then to submission order. Confidence alone is the wrong
   rule here: a statement running off the edge of the frame is read with perfect
   confidence and is simply incomplete, and it would beat the photograph that
   captured the whole thing.
5. **The response says which photograph each field came from**, as
   `source_photo` on every field result, and reports every submitted photograph
   in a `photos` array with its orientation, its confidence, and its error if it
   had one.
6. **A photograph that cannot be read does not fail the submission** while
   another one did read. It is reported as a failed entry in `photos`. Only when
   no photograph could be read at all does the request fail, with its own error
   code `all_photos_unreadable` (FR-9).
7. **The cap is three, configurable as `TTB_MAX_LABEL_PHOTOS`.** `(Assumption)`
   More than the cap is refused before any photograph is processed, with the
   limit named (NFR-7, FR-9).
8. **The batch path stays at one photograph per row this session.** See
   Consequences.

## Alternatives considered

**Stitch the photographs into one image.** Rejected, and it is the alternative
that looks most attractive from a distance: one image means one read and no
merge rule. It is rejected for three reasons. It needs feature matching and a
homography or cylindrical warp estimate, which is a substantial piece of image
processing and a new dependency surface on a path that ADR 0003 keeps
deliberately small. It works badly on the input it would be given: stitching
assumes overlap between frames, and an agent photographing the front and the
back of a bottle produces two frames with no overlap at all. And **its failure
mode is silent.** A stitch that misaligns produces a plausible image with
duplicated or dropped text, which then reads as a label whose wording is wrong.
That failure is indistinguishable in the result from a genuine compliance
defect, which is the single worst property a check of this kind can have. The
union of independently read photographs cannot fail that way: a photograph that
reads badly reads badly on its own and is reported as its own entry.

**Concatenate the raw OCR text of all photographs and parse the union once.**
This is the simpler reading of "a union of the extracted text" and it was
rejected on inspection of what the parser does with it. `app/parse.py` finds the
brand name by comparing type sizes across the text it is given, and finds the
warning by taking the first line matching the prefix and consuming forward until
the statement's length is reached. Concatenating two photographs breaks both:
the warning would be consumed across a photograph boundary, and a back label's
lines would compete with a front label's on size in one flat list where
adjacency no longer means anything. Parsing each photograph and merging the
fields keeps every heuristic operating on the evidence it was designed for.

**Let the agent choose which photograph is authoritative.** Rejected as a
usability cost with no accuracy benefit. It asks an agent to answer a question
the tool is better placed to answer, on every check, and NFR-4's benchmark is
someone who should not have to.

**Take more than three photographs.** Rejected for now, not on principle. Three
covers front, back, and the seam between them, which is what the geometry
actually requires; the number is configurable and the assumption is recorded.

## Consequences

**Positive**

- A label whose required elements are not all on one face can be checked, which
  is a case 27 CFR 16.21 explicitly contemplates and the prototype could not
  previously handle at all.
- An agent can work around cylinder distortion by photographing the parts a
  single frame cannot show flat, without the tool having to model the geometry.
- One bad photograph among good ones costs nothing, which is the FR-8 rule
  applied inside one label.
- One photograph behaves exactly as it did. The wire format for a single
  photograph is unchanged, and the tests that covered it are unchanged.

**Negative**

- Three photographs is roughly three times the work of one. On a session runner
  a single photograph measures about 1.3 seconds end to end with orientation
  detection on; three measure proportionally more, and NFR-1's target is about 5
  seconds. The margin is real but it is not large, and it is measured rather
  than assumed: `docs/07_TEST_STRATEGY.md` section 4.
- The single-label envelope limit rises from `TTB_MAX_UPLOAD_BYTES` to three
  times it, because the middleware that reads Content-Length cannot count the
  parts without reading the body it is trying not to read. Each photograph is
  still checked exactly against `TTB_MAX_UPLOAD_BYTES` after parsing. The
  loosening is recorded in the middleware docstring rather than left to be
  discovered.
- The response grows: a `photos` array and a `source_photo` on each field. A
  client that ignores both still reads exactly what it read before.

**Risks accepted**

- **That the merge rule reports the wrong reading.** Two photographs can both
  show a field and disagree, and the rule above picks one. The specific residual
  case is the warning: if two photographs both show the whole statement and one
  is misread into something *longer* than the other, length picks the misread.
  The mitigation is disclosure rather than cleverness, which is this project's
  standing pattern: the response says which photograph each value came from, so
  an agent looking at a surprising result can see where it came from and take
  the photograph again.
- **That three photographs is the wrong number.** `(Assumption)` No source
  states how many an agent would take. It is configurable, and the refusal names
  the limit.
- **That this is a workaround and not a fix.** Cylinder and perspective
  dewarping is still not attempted, and how much accuracy is lost without it is
  unmeasured on real artwork. That is recorded as OQ-21 rather than estimated.

**Deliberately out of scope this session**

- **The batch path stays at one photograph per row.** FR-8's CSV contract (A-14)
  keys application data on image filename, so a row that referred to several
  images would need a new column shape, a new reconciliation rule for partially
  matched groups, and a new answer for what a per-row error means when one of
  three photographs failed. None of that is hard; all of it is a second design
  with its own assumptions, and no source asks for it. It is stated in the FR-8
  notes rather than left to be discovered by an agent who tries it, and the
  behaviour is asserted in
  `backend/tests/test_multi_photo.py::TestTheBatchPathIsUnaffected`.

## References

- [../03_REQUIREMENTS.md](../03_REQUIREMENTS.md) FR-1, FR-8, FR-9, NFR-1, NFR-7
- [../04_USER_STORIES.md](../04_USER_STORIES.md) US-22
- [../02_PROJECT_SCOPE.md](../02_PROJECT_SCOPE.md) SG-1
- [../ASSUMPTIONS.md](../ASSUMPTIONS.md) A-15, A-16
- [../OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md) OQ-21
- [0003-local-ocr-default-bedrock-optional.md](0003-local-ocr-default-bedrock-optional.md)
- [0006-batch-execution-model.md](0006-batch-execution-model.md)
- 27 CFR 16.21, retrieved from eCFR on 2026-08-20
