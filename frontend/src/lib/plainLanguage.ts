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

export const MESSAGES: Record<string, string> = {
  unreadable_image: "We couldn't read this label. Try a clearer image.",
  no_text_found: "We couldn't find any text on this image. Try a clearer image.",
  unsupported_media_type: 'That file is not an image we can read. Send a JPEG, PNG, WebP or TIFF.',
  // The server sends this code for three different things and names which in
  // its message; `plainMessage` reads that to say what was actually too large
  // (code review finding 30). This is the one-file case.
  file_too_large: 'That file is too large. Send a smaller one.',
  // The single-label envelope, and the batch envelope, each too large as a whole.
  submission_too_large:
    'Those files are too large to send together. Send fewer photos of the label, or smaller ones.',
  batch_envelope_too_large:
    'That batch is too large to send in one go. Split it into smaller batches and send them one after another.',
  // The three the single upload can meet that had no line until v1.3.0
  // (code review finding 22). Each says what to do next.
  no_files: 'Nothing was uploaded. Choose the label application, a photo of the label, or both.',
  no_label_to_check:
    'The application you uploaded has no label picture we could read, so there is nothing to check yet. Add a photo of the label.',
  too_many_application_documents:
    'More than one of these files reads as a label application. Keep one application for one label, plus any photos of it.',
  all_photos_unreadable:
    "We couldn't read any of the photos of this label. Try clearer photos, in better light.",
  too_many_photos: 'That is more photos than we can read for one label. Remove one and try again.',
  batch_too_large: 'That is too many labels for one batch. Split it and send them in groups.',
  empty_batch: 'Nothing was uploaded. Choose the label applications, the label images, or both.',
  invalid_submission: 'Something the check needs was missing from the form.',
  malformed_upload: 'The upload did not arrive in one piece. Try sending it again.',
  // The two batch rows that cannot be checked (ADR 0020). Files that share a
  // name before the extension are one label, and a label holds one application
  // and one image; the unmatched and missing cases of ADR 0009 are gone,
  // because a file on its own is a valid row now.
  duplicate_application_document:
    'More than one file with this name reads as a label application, so which one applies is unclear and nothing was compared.',
  duplicate_label_stem:
    'More than one file with this name reads as a label image. This page checks one image for each label; check a label with several photos on the Check one label tab.',
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
export function plainMessage(code: string | undefined, message?: string | null): string {
  if (code === 'file_too_large' && message) {
    // Keyed on the server's own wording for the two envelope cases, because
    // the code is the same for all three and the limit string names only a
    // byte count. An unrecognised wording falls through to the one-file line.
    if (/fewer photographs/i.test(message)) return MESSAGES.submission_too_large
    if (/smaller batches/i.test(message)) return MESSAGES.batch_envelope_too_large
  }
  if (code && code in MESSAGES) return MESSAGES[code]
  return "We couldn't check this label. Try again, and tell your administrator if it keeps happening."
}

/** The message shown when the request never reached the API at all. */
export const NETWORK_MESSAGE =
  "We couldn't reach the label checker. Check your connection and try again."
