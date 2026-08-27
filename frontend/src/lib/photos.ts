/**
 * What to say about each submitted photograph of one label (ADR 0007, A-15).
 *
 * Separate from the component that renders it because these are decisions
 * about wording rather than about markup, and they are worth testing directly:
 * "we turned it 90 degrees" is a sentence an agent reads and acts on, and it
 * should not need a render to check.
 */
import { plainMessage } from './plainLanguage'
import type { PhotoResult } from '../types'

/** What was done to one photograph, as a sentence, or null if nothing was. */
export function photoNote(photo: PhotoResult): string | null {
  if (!photo.text_found) {
    return `We could not read this photo. ${plainMessage(photo.error?.code)}`
  }
  const turned: string[] = []
  if (photo.orientation.exif_transposed) {
    turned.push('it was saved sideways by the camera')
  }
  if (photo.orientation.rotation_degrees > 0) {
    turned.push(`we turned it ${photo.orientation.rotation_degrees} degrees to read it`)
  }
  if (!turned.length) return null
  // Capitalized here rather than in the parts, so the parts stay readable.
  const sentence = turned.join(', and ')
  return `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)}.`
}

/** True when there is anything worth telling the agent about the photographs. */
export function hasPhotoNotes(photos: PhotoResult[]): boolean {
  return photos.length > 1 || photos.some((photo) => photoNote(photo) !== null)
}

/**
 * "Read from photo 2", for a field card, when more than one photograph was
 * submitted.
 *
 * Suppressed for a single photograph, where "read from photo 1" says nothing
 * an agent does not already know.
 */
export function sourceLabel(sourcePhoto: number | null, photoCount: number): string | null {
  if (photoCount < 2 || sourcePhoto === null) return null
  return `Read from photo ${sourcePhoto}`
}
