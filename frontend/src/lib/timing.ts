/**
 * What the interface is allowed to say about how long a check took (NFR-1).
 *
 * **The rule: report what was measured, and never name a phase nobody
 * measured.** The panel used to print the browser's wall clock, subtract the
 * server's figure, and tell the agent the remainder was "sending the image and
 * receiving the answer". Two things were wrong with that, and the second is the
 * one that matters.
 *
 * The server's figure was not what it claimed: it measured the label-side OCR
 * span, not the request. And the difference was not the network. A control POST
 * of the same 382 KB file to a path that processes nothing crossed the wire in
 * 68 to 111 ms; the sentence was attributing about three and a half seconds of
 * document parsing and a duplicated OCR pass to a connection that was fine.
 *
 * An invented explanation is worse than no explanation. It sends an agent, or
 * whoever they complain to, looking in the wrong place, and it is exactly the
 * kind of small dishonesty a sceptical user learns to distrust a tool over.
 *
 * So there are two numbers and one honest name for their difference. The wall
 * clock is what the agent waited. The server's total is what the server spent.
 * What is left is time in the browser and on the wire, which is what it is:
 * this code has not measured it and does not pretend to have.
 */
import type { PhaseTimings } from '../types'

/** One measured span, ready to render. */
export interface Span {
  label: string
  ms: number
}

/**
 * The sentence under the headline time.
 *
 * The difference is named rather than explained. "Time in the browser and on
 * the wire" is a location, which is true; "sending the image" was a mechanism,
 * which was not.
 */
export function timingSummary(seconds: number, serverMs: number): string {
  const elsewhere = Math.max(seconds * 1000 - serverMs, 0)
  return (
    `${serverMs.toFixed(0)} ms of that was inside the checker. ` +
    `The other ${elsewhere.toFixed(0)} ms was in your browser and on the network.`
  )
}

/**
 * The phases worth showing, largest first, with anything that took no time left
 * out.
 *
 * Filtered rather than listed in full because a request takes one path through
 * the pipeline and the phases belonging to the other paths are honestly zero. A
 * row of zeroes is not disclosure; it is noise that buries the one line an
 * agent or an operator is looking for.
 *
 * `unaccounted_ms` is kept even when it is small, and it is deliberately named
 * as unaccounted rather than folded into the nearest phase. It is the only
 * figure here that was arrived at by subtraction, and saying so is what lets a
 * reader trust the rest.
 */
export function spans(timings: PhaseTimings): Span[] {
  const measured: Span[] = [
    { label: 'Sorting what you uploaded', ms: timings.classify_ocr_ms },
    { label: 'Reading the application document', ms: timings.document_pdfium_ms },
    { label: 'Reading the application as an image', ms: timings.document_ocr_ms },
    { label: 'Reading the document pages as images', ms: timings.page_ocr_ms },
    { label: 'Reading the label artwork in the application', ms: timings.artwork_ocr_ms },
    { label: 'Reading the label', ms: timings.label_ocr_ms },
    { label: 'Comparing the fields', ms: timings.compare_ms },
  ].filter((span) => span.ms >= 0.5)

  measured.sort((a, b) => b.ms - a.ms)
  if (timings.unaccounted_ms >= 0.5) {
    measured.push({ label: 'Not attributed to any step', ms: timings.unaccounted_ms })
  }
  return measured
}

/**
 * How the reading work is described in one clause, for the phase list's caption.
 *
 * The pass count is here because it is the number that made the 2026-08-30
 * finding legible: the same picture was being read twice, and no duration on
 * its own says that.
 */
export function readingNote(timings: PhaseTimings): string {
  const passes = timings.ocr_passes
  const noun = passes === 1 ? 'pass' : 'passes'
  return `${timings.ocr_ms.toFixed(0)} ms of reading, over ${passes} ${noun}.`
}
