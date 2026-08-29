# ADR 0003: Local OCR as the default extraction path, Bedrock fallback optional and off

| | |
| --- | --- |
| Status | Accepted |
| Date | 2026-08-20 |
| Author | Kimberly D. Kight |
| Decision reference | D-4 |

## Context

Text has to come off the label image before anything can be compared. The choice
of how is constrained by three statements from the interviews, two of which are
about failure rather than preference.

**The network blocks outbound traffic.** Marcus Williams: "our network blocks
outbound traffic to a lot of domains, so keep that in mind if you're thinking
about cloud APIs." He gives the precedent directly: "During the scanning vendor
pilot, half their features didn't work because our firewall blocked connections
to their ML endpoints. Classic." [Source: Marcus Williams interview]

**Latency decides adoption.** The same pilot took "30, 40 seconds sometimes to
process a single label," and agents abandoned it. "If we can't get results back
in about 5 seconds, nobody's going to use it."
[Source: Sarah Chen interview]

**Imperfect images are a known gap.** Jenny Park: "it would be amazing if the
tool could handle images that aren't perfectly shot. I've seen labels that are
photographed at weird angles, or the lighting is bad, or there's glare on the
bottle." She qualifies it herself: "this is maybe out of scope for a prototype."
[Source: Jenny Park interview]

A design that depends on an external API fails the first constraint and repeats
a failure these stakeholders have already lived through.

## Decision

Run **OCR locally inside the container** as the default path, using Tesseract
through `pytesseract` with OpenCV preprocessing, making **no outbound network
calls**.

Provide an **optional fallback to a vision model on Amazon Bedrock**, disabled
by default and enabled only by setting `TTB_ENABLE_BEDROCK_FALLBACK`.

## Alternatives considered

### A cloud OCR or document AI API as the primary path

Examples include Amazon Textract and equivalent services from other providers.
These generally handle poor image quality better than local OCR, which speaks
directly to Jenny's request.

Not chosen as the primary path because it fails Marcus's constraint outright. An
architecture whose core function requires reaching an external endpoint is the
architecture that already failed here once. The prototype must work with egress
blocked (NFR-3).

### A vision language model as the primary path

Would likely handle angled, poorly lit, and glared photographs better than
Tesseract, and could extract labeled fields directly rather than requiring
field parsing after OCR.

Not chosen as the primary path for the same egress reason, and for a second
reason specific to this domain: a generative model can return a plausible value
that was never on the label. In a compliance workflow that failure mode is worse
than returning nothing, because a fabricated value is not obviously wrong and an
agent may act on it. Deterministic OCR fails visibly; generative extraction can
fail invisibly.

### Local OCR only, with no fallback at all

The simplest option, and it fully satisfies the egress constraint.

Not chosen because it leaves no path for the images Jenny describes. Keeping the
fallback available, off by default, records the option without putting it on the
committed path.

### A commercial OCR engine running locally

Would satisfy the egress constraint and may read poor images better than
Tesseract.

Not chosen because of licensing and procurement overhead disproportionate to a
prototype, and because it would introduce a dependency the agency has not
evaluated.

**No accuracy or latency comparison between these options was measured.** The
reasoning above rests on the stated constraints and on the known behaviour of
each execution model, not on benchmark results. Measuring Tesseract's actual
per-field accuracy against the sample set is required work; see
[../07_TEST_STRATEGY.md](../07_TEST_STRATEGY.md) section 3.

## Consequences

**Positive**

- The default path works with egress blocked, which is the environment Marcus
  describes.
- No per-request API cost and no external rate limit.
- No label artwork leaves the container on the default path, which is what makes
  "nothing is persisted" a complete statement about data handling rather than a
  partial one.
- Latency is bounded by local CPU rather than by an external service, which is
  the variable that made the previous pilot unusable.

**Negative**

- Tesseract is likely to read angled, poorly lit, or glared photographs worse
  than a cloud service would. This is the direct cost of the egress constraint,
  and it is why SG-1 is a stretch goal rather than committed scope.
- OCR runs on the container's CPU, so task sizing directly affects whether the
  5-second target is met.
- The container image is larger, since it carries Tesseract, its English
  language data, and OpenCV's runtime libraries.
- Preprocessing quality, such as deskewing and thresholding, becomes the
  project's responsibility rather than a vendor's.

**Risks accepted**

- That Tesseract's accuracy on real label artwork proves insufficient. This is
  unmeasured and is the largest open technical risk in the prototype. It is why
  accuracy is measured and published per field rather than asserted (US-21).

  **Partly realized, 2026-08-26.** The first photograph of a real bottle
  submitted to the deployed prototype returned none of the five fields. Three
  causes were found by inspecting the photograph, and two are fixed: the
  photograph was sideways and carried its turn in an EXIF tag OpenCV ignores
  (now corrected, with Tesseract's orientation and script detection measured at
  46 of 48 against a best-of-four confidence score at 7 of 48), and the warning
  was set in a narrow column with printer's hyphens that the exact comparison
  read as altered wording (now rejoined). Both are recorded as assumption A-15.

  **Realized again, and differently, 2026-08-28.** A photograph of a Ketel One
  back label, crisp and flat and with the government warning in clear capitals,
  returned the brand as `Sal.`, the class as shrapnel from the bottom fine
  print, and the warning as not found. This one was not the artwork. It was the
  preprocessing this ADR calls the project's responsibility, and it failed in
  the way that consequence predicts: adaptive thresholding at a 31-pixel block
  suits rendered type and destroys a soft-contrast photograph. Because the
  orientation call was being made on the thresholded image, it was being made on
  noise, and over the twelve-label set degraded into a photograph-like fixture
  it was right in 0 of 48 cases against 44 of 48 on the plain grayscale. v1.0.1
  moves the call to the grayscale and stops trusting preprocessing to be an
  improvement: both the preprocessed and the plain image are read and the higher
  scoring result is kept.

  The lesson is narrower than "Tesseract is insufficient" and worth stating
  exactly. Every figure this ADR and A-15 quote was measured on artwork rendered
  by `samples/labelmaker.py`. A measurement taken on rendered type does not
  transfer to photographs, and the accuracy risk above stays open: one label
  read correctly is still not a measurement.

  The third is not fixed and is this risk in its original form: the label wraps
  a round bottle, so the far edges compress and distort, and no single
  photograph shows the label flat. Perspective and cylinder dewarping are
  deliberately not attempted, for the reason this ADR gives for keeping SG-1 a
  stretch goal. [ADR 0007](0007-multi-photo-single-label.md) works around it by
  accepting up to three photographs of the same label rather than correcting
  the geometry of one.
- That enabling the Bedrock fallback later reintroduces every constraint this
  decision avoids: egress, data leaving the boundary, FedRAMP status, and
  fabricated values. Mitigated by making it off by default, by requiring the
  result to disclose when it was used (NFR-3), and by keeping it out of
  committed scope.

## References

- [../03_REQUIREMENTS.md](../03_REQUIREMENTS.md) FR-1, NFR-3
- [../05_ARCHITECTURE.md](../05_ARCHITECTURE.md) sections 3 and 7
- [../06_SECURITY_AND_COMPLIANCE.md](../06_SECURITY_AND_COMPLIANCE.md) section 6.3
- [../02_PROJECT_SCOPE.md](../02_PROJECT_SCOPE.md) SG-1, SG-2
