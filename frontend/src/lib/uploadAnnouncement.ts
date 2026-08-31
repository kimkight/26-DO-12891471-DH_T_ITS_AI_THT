/**
 * What the live region says after an upload has been sorted (FR-12, NFR-5).
 *
 * Its own module rather than an export beside the component, because it is a
 * decision about wording rather than about markup and it is worth asserting
 * without rendering anything. Every accepted file is named with what it was
 * taken to be, which is FR-12's accessibility criterion: an agent who cannot
 * see the list has no other way to learn that their COLA form was read as a
 * label.
 */
import { plainMessage } from './plainLanguage'
import type { ClassificationResult, FileClassification } from '../types'

/** The short name for each side, for the chip beside a file and for the announcement. */
export const SIDES: Record<FileClassification['classified_as'], string> = {
  application_document: 'Label application',
  label_image: 'Label image',
}

export function announce(result: ClassificationResult): string {
  const sorted = result.files
    .map((entry) => `${entry.filename}, read as a ${SIDES[entry.classified_as].toLowerCase()}`)
    .join('. ')
  // A file classified as the application that could not be read is announced as
  // that, not as an absence: the agent uploaded an application and it did not
  // arrive, which is a different thing to act on (FR-9).
  if (result.application_error) {
    return `${sorted}. ${plainMessage(result.application_error.code)}`
  }
  const document = result.application_document
  if (!document) {
    return `${sorted}. No application was uploaded, so type the values you want checked.`
  }
  const found = document.fields.filter((entry) => entry.found_on_document)
  if (!found.length) {
    return `${sorted}. The application was read, but it did not carry any of the values we compare. Type them in yourself.`
  }
  return `${sorted}. ${found.length} of ${document.fields.length} values filled in from the application: ${found
    .map((entry) => entry.display_name)
    .join(', ')}. Check them and change anything that is wrong.`
}
