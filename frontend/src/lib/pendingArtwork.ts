/**
 * The values the artwork will supply, on a document whose artwork is not read
 * yet (ADR 0017).
 *
 * The prefill pass takes the application document's text layer and stops. Two
 * of the five values are usually not in that text layer at all: assumption A-17
 * is that TTB F 5100.31 carries no alcohol content and no net contents boxes,
 * so on the author's own filing both are printed on the artwork affixed to the
 * application rather than typed into a numbered item. Reading that artwork is
 * what the check does anyway, so the prefill pass no longer pays for it a
 * second time.
 *
 * **What this module exists to prevent is the interface calling those two a
 * gap.** A gap is a value nothing supplied and the agent has to type, and the
 * interface treats it as the only work left on the screen: the field opens,
 * focus moves to it, and a live region says it was not found. None of that is
 * true of a value that is about to be read; it would be the tool asking an
 * agent to do work it is already doing, one second before doing it.
 *
 * So a field is pending, not missing, when three things hold: the document
 * carried pictures, they were deliberately not read, and its text layer did not
 * state the value. The result populates the field when the check runs, which is
 * what the agent sees.
 */
import type { ApplicationData, ApplicationDocumentResult } from '../types'

/**
 * The values embedded label artwork can supply (ADR 0010).
 *
 * Mirrors `ARTWORK_FIELDS` in `backend/app/application_form.py`. The beverage
 * type is deliberately not one of them: item 5 is three check boxes, a label
 * does not print "distilled spirits" as a form answer, and inferring one from
 * the artwork would be the guess FR-1 forbids.
 */
export const ARTWORK_FIELDS: (keyof ApplicationData)[] = [
  'brand_name',
  'class_type',
  'alcohol_content',
  'net_contents',
]

/**
 * The fields this document will answer from its artwork when the check runs.
 *
 * Empty for every reading that did read the artwork, so a server that predates
 * ADR 0017, or the `POST /api/read-application` route that still reads
 * everything, behaves exactly as it did.
 */
export function pendingFromArtwork(
  document: ApplicationDocumentResult | null | undefined,
): (keyof ApplicationData)[] {
  if (!document || document.artwork_read !== false || !document.artwork_images_found) return []
  const found = new Set(
    document.fields.filter((entry) => entry.found_on_document).map((entry) => entry.name),
  )
  return ARTWORK_FIELDS.filter((name) => !found.has(name))
}
