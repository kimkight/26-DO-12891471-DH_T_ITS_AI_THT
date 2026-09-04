/**
 * What to say about each submitted photograph of one label (ADR 0007, A-15).
 *
 * Separate from the component that renders it because these are decisions
 * about wording rather than about markup, and they are worth testing directly:
 * "we turned it 90 degrees" is a sentence an agent reads and acts on, and it
 * should not need a render to check.
 */
import { plainMessage } from './plainLanguage'
import type { ApplicationDocumentResult, PhotoResult } from '../types'

/** What was done to one photograph, as a sentence, or null if nothing was. */
export function photoNote(photo: PhotoResult): string | null {
  const noun = photo.origin === 'application_artwork' ? 'label artwork' : 'photo'
  if (!photo.text_found) {
    return `We could not read this ${noun}. ${plainMessage(photo.error?.code)}`
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

/**
 * True when there is anything worth telling the agent about the images read.
 *
 * The artwork case always qualifies: an agent who uploaded one file and got
 * five results has to be able to see what the label side actually was
 * (ADR 0010).
 */
export function hasPhotoNotes(photos: PhotoResult[]): boolean {
  return (
    photos.length > 1 ||
    photos.some((photo) => photo.origin === 'application_artwork') ||
    photos.some((photo) => photoNote(photo) !== null)
  )
}

/**
 * What the list of images is called, which is not always "your photos".
 *
 * When the check ran on artwork lifted out of the application document there is
 * no photograph at all, and calling it one would be the interface telling the
 * agent something untrue about what was checked (ADR 0010).
 */
export function photoListHeading(photos: PhotoResult[]): string {
  if (photos.every((photo) => photo.origin === 'application_artwork')) {
    return photos.length === 1
      ? 'The label artwork from the application'
      : `The ${photos.length} pieces of label artwork from the application`
  }
  return photos.length === 1 ? 'Your photo' : `Your ${photos.length} photos`
}

/**
 * How one entry in that list is named.
 *
 * A piece of artwork is named by where it sat in the document and how big it
 * is, because a filing that embeds its labels as separate panels has several
 * and "label artwork from the application" three times over tells an agent
 * nothing about which is which (ADR 0010 as amended).
 */
export function photoItemLabel(photo: PhotoResult): string {
  if (photo.origin !== 'application_artwork') return `Photo ${photo.index}`
  const panel = photo.artwork_panel
  return panel
    ? `Label artwork on page ${panel.page} of the application, ${panel.width} by ${panel.height} pixels`
    : 'Label artwork from the application'
}

/**
 * What else was in the application, and what happened to it (ADR 0010 as
 * amended, #121).
 *
 * The response lists every embedded picture that was set aside with the
 * reason, and every one that cleared the floor and was not read. An agent
 * looking at a value the tool did not find is entitled to that table without
 * instrumenting anything: on a real filing five of six pictures were set
 * aside and nothing on screen said so. Null when there is nothing to say,
 * which is the ordinary case.
 */
export function artworkNote(document: ApplicationDocumentResult | null | undefined): string | null {
  if (!document) return null
  const rejected = document.artwork_images_rejected ?? []
  const unread = (document.artwork_images_accepted ?? []).filter((image) => image.status !== 'read')
  const parts: string[] = []
  if (rejected.length) {
    const sizes = rejected.map((image) => `${image.width} by ${image.height} on page ${image.page}`)
    parts.push(
      `${rejected.length === 1 ? 'One picture' : `${rejected.length} pictures`} in the application ${
        rejected.length === 1 ? 'was' : 'were'
      } set aside as too small to be label artwork: ${sizes.join('; ')}.`,
    )
  }
  if (unread.length) {
    const sizes = unread.map(
      (image) =>
        `${image.width} by ${image.height} on page ${image.page} (${UNREAD_REASONS[image.status]})`,
    )
    parts.push(
      `${unread.length === 1 ? 'One picture' : `${unread.length} pictures`} cleared the size floor and ${
        unread.length === 1 ? 'was' : 'were'
      } not read as label artwork: ${sizes.join('; ')}.`,
    )
  }
  return parts.length ? parts.join(' ') : null
}

const UNREAD_REASONS: Record<'no_text' | 'not_read' | 'undecodable' | 'read', string> = {
  no_text: 'no text was found on it',
  not_read: 'past the limit on how many pictures are read',
  undecodable: 'it could not be decoded',
  read: 'read',
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
