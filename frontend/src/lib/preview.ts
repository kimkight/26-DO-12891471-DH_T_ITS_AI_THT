/**
 * Which uploads the browser can draw a preview of (code review finding 32).
 *
 * TIFF is accepted by the API and read by the server, and no browser renders
 * it: an `<img>` pointed at one shows the broken-image glyph, which was the
 * one unacceptable option. A file outside this set gets an honest placeholder
 * naming its type instead of a preview. Kept apart from the component so the
 * decision can be asserted without rendering anything.
 */

const BROWSER_DECODES = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/gif'])

/**
 * Whether an object URL can be made at all. jsdom has no `createObjectURL`,
 * and a component that assumed it would throw in every test; in a browser it
 * is always true, and the Chromium accessibility run exercises the real path.
 */
export const CAN_PREVIEW = typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function'

export function canPreview(file: File): boolean {
  return CAN_PREVIEW && BROWSER_DECODES.has(file.type)
}

/** The placeholder line for a file the browser cannot draw, naming what it is. */
export function previewPlaceholder(file: File): string {
  if (file.type === 'image/tiff') {
    return 'TIFF image; browsers cannot show a preview of it, and the server reads it as usual.'
  }
  if (!CAN_PREVIEW) return 'Preview unavailable in this browser.'
  return `${file.type || 'This file'} cannot be previewed here; the server reads it as usual.`
}
