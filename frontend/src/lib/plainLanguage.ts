/**
 * API error codes rendered as something an agent can act on (FR-9, NFR-4).
 *
 * FR-9 requires a clear message naming the problem, and the API already
 * supplies one. These are not translations of it; they are the shorter,
 * plainer form for the top of the screen, and the API's own message is shown
 * underneath as the detail. Where the two disagree the API is right, because it
 * knows which limit was exceeded.
 *
 * Sarah Chen's benchmark governs the wording: something a 73-year-old
 * first-time user "could figure out". No status codes, no error codes, no
 * MIME types in the sentence an agent reads first.
 */

const MESSAGES: Record<string, string> = {
  unreadable_image: "We couldn't read this label. Try a clearer photo.",
  no_text_found: "We couldn't find any text on this image. Try a clearer photo.",
  unsupported_media_type: 'That file is not an image we can read. Send a JPEG, PNG, WebP or TIFF.',
  file_too_large: 'That image is too large. Send a smaller one.',
  all_photos_unreadable:
    "We couldn't read any of the photos of this label. Try clearer photos, in better light.",
  too_many_photos: 'That is more photos than we can read for one label. Remove one and try again.',
  batch_too_large: 'That is too many labels for one batch. Split it and send them in groups.',
  empty_batch: 'No label images were attached. Choose the images, then the application data file.',
  invalid_application_csv:
    'We could not read the application data file. Check that it is a CSV with the expected columns.',
  invalid_submission: 'Something the check needs was missing from the form.',
  malformed_upload: 'The upload did not arrive in one piece. Try sending it again.',
  missing_application_row: 'No row in the application data file matches this image.',
  unmatched_application_row: 'The application data file lists this file, but it was not attached.',
  duplicate_application_row:
    'The application data file has more than one row for this image, so nothing was compared.',
  verification_failed: "We couldn't check this label. Try submitting it on its own.",
}

/**
 * The plain-language line for an error code.
 *
 * The fallback is deliberately not "an unknown error occurred". An agent's next
 * action is the same whether or not this build recognizes the code, so the
 * fallback says what that action is.
 */
export function plainMessage(code: string | undefined): string {
  if (code && code in MESSAGES) return MESSAGES[code]
  return "We couldn't check this label. Try again, and tell your administrator if it keeps happening."
}

/** The message shown when the request never reached the API at all. */
export const NETWORK_MESSAGE =
  "We couldn't reach the label checker. Check your connection and try again."
