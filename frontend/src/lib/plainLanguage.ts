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
  empty_batch: 'No label images were attached. Choose the images, then a COLA document for each.',
  invalid_submission: 'Something the check needs was missing from the form.',
  malformed_upload: 'The upload did not arrive in one piece. Try sending it again.',
  // The batch pairing failures (ADR 0009). Each names the file the agent has to
  // do something about, because a batch of 300 is not a place to go hunting.
  missing_application_documents:
    'No COLA documents were attached. Each label image needs one with the same name, so photo.png goes with photo.pdf.',
  missing_application_document:
    'No COLA document has the same name as this image, so there was nothing to compare it against.',
  unmatched_application_document:
    'This COLA document has no label image with the same name, so nothing was checked for it.',
  duplicate_application_document:
    'More than one COLA document has this name, so which one applies is unclear and nothing was compared.',
  duplicate_label_stem:
    'More than one image has this name before its file extension, so which label the document belongs to is unclear.',
  verification_failed: "We couldn't check this label. Try submitting it on its own.",
  unsupported_application_document:
    'That file is not one we can read as a label application. Send a PDF, or a photo or scan of the form.',
  unreadable_application_document:
    "We couldn't read that label application. Check the file, or type the values in yourself.",
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
