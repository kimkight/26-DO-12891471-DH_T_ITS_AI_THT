/**
 * "Upload the label application instead of typing it" (FR-11, ADR 0008, US-23).
 *
 * The values an agent is asked to type are the values the applicant already
 * submitted to TTB on the label application, TTB F 5100.31. This accepts a copy
 * of that document, or of the Public COLA Registry printout of an approved one,
 * and reads it locally.
 *
 * **This is not the COLA integration OOS-1 excludes.** Nothing here reaches
 * TTB. The file goes to this application's own API, which parses it in process
 * with no credentials and no outbound call, and keeps nothing.
 *
 * **What it does with what it read.** It fills the same fields the agent would
 * have typed into and marks each one as read from the application form. It does
 * not check anything, and it does not submit anything. The agent reads the
 * fields, corrects whatever is wrong, and presses the same button they would
 * have pressed anyway. That is FR-3's philosophy applied one step earlier: the
 * tool reads, the agent judges.
 */
import { useId, useState } from 'react'
import { DropZone } from './DropZone'
import { ErrorMessage } from './ErrorMessage'
import { readApplication } from '../lib/api'
import type { UiError } from '../lib/api'
import type { ApplicationDocumentResult } from '../types'

/** PDF plus the image types, mirroring the API's accepted document types. */
export const ACCEPTED_DOCUMENTS = 'application/pdf,image/jpeg,image/png,image/webp,image/tiff'

/** How each extraction path is described to an agent, in their words. */
const PATHS: Record<ApplicationDocumentResult['extraction_path'], string> = {
  form_fields: 'read from the boxes you filled in on the form',
  embedded_text: 'read from the text in the file',
  ocr: 'read by looking at the pages as pictures, the way we read a label photo',
}

interface Props {
  /** Called with what the document said, so the form fields can be filled. */
  onParsed: (document: ApplicationDocumentResult) => void
  /** Called when the agent takes the document back off the form. */
  onCleared: () => void
}

export function ApplicationUpload({ onParsed, onCleared }: Props) {
  const headingId = useId()
  const [file, setFile] = useState<File | null>(null)
  const [reading, setReading] = useState(false)
  const [document, setDocument] = useState<ApplicationDocumentResult | null>(null)
  const [error, setError] = useState<UiError | null>(null)
  const [spoken, setSpoken] = useState('')

  async function choose(chosen: File | null) {
    setDocument(null)
    setError(null)
    if (!chosen) {
      setFile(null)
      setSpoken('')
      onCleared()
      return
    }
    setFile(chosen)
    setReading(true)
    setSpoken('Reading the label application.')
    const outcome = await readApplication(chosen)
    setReading(false)
    if (outcome.error || !outcome.document) {
      setError(outcome.error)
      // The plain-language message already names the problem and says the typed
      // path is still open, so it is announced as it stands rather than
      // restated in different words (FR-9, NFR-5).
      setSpoken(outcome.error?.message ?? '')
      onCleared()
      return
    }
    setDocument(outcome.document)
    onParsed(outcome.document)
    const found = outcome.document.fields.filter((entry) => entry.found_on_document)
    setSpoken(
      found.length
        ? `${found.length} of ${outcome.document.fields.length} values filled in from the application form: ${found
            .map((entry) => entry.display_name)
            .join(', ')}. Check them and change anything that is wrong.`
        : 'The application form was read, but it did not carry any of the values we compare. Type them in yourself.',
    )
  }

  function clear() {
    void choose(null)
  }

  const found = document?.fields.filter((entry) => entry.found_on_document) ?? []
  const missing = document?.fields.filter((entry) => !entry.found_on_document) ?? []

  return (
    <section className="application-upload" aria-labelledby={headingId}>
      <h3 className="application-upload__heading" id={headingId}>
        Upload the label application (COLA form) instead
      </h3>
      <p className="field__hint" id={`${headingId}-hint`}>
        If you have the applicant&apos;s TTB F 5100.31, or the Public COLA Registry printout for it,
        attach it here and we will fill in what it says. You can change anything we get wrong. The
        file is read here and is not sent to TTB or kept.
      </p>

      <DropZone
        label="Label application"
        hint="Drag a file here, or choose one. PDF, or a photo or scan of the form."
        accept={ACCEPTED_DOCUMENTS}
        files={file ? [file] : []}
        onFiles={(chosen) => void choose(chosen[0] ?? null)}
      />

      {file ? (
        <button className="button button--quiet" type="button" onClick={clear}>
          Remove this application form
        </button>
      ) : null}

      {reading ? <p className="field__hint">Reading the application form...</p> : null}
      {error ? <ErrorMessage error={error} /> : null}

      {document ? (
        <div className="application-upload__result">
          <p className="application-upload__summary">
            {found.length} of {document.fields.length} values were filled in from this form,{' '}
            {PATHS[document.extraction_path]}
            {document.pages_read > 1 ? ` over ${document.pages_read} pages` : ''}. Check each one
            below before you run the check.
          </p>
          {document.class_type_code ? (
            <p className="field__hint">
              The form gives the class or type code as {document.class_type_code}. The description
              is what gets compared.
            </p>
          ) : null}
          {document.fanciful_name ? (
            <p className="field__hint">
              Fanciful name on the application: {document.fanciful_name}. It is not one of the
              fields we compare.
            </p>
          ) : null}
          {missing.length ? (
            <>
              <p className="application-upload__summary">
                Not on this form, so you will need to enter{' '}
                {missing.map((entry) => entry.display_name.toLowerCase()).join(', ')}:
              </p>
              <ul className="application-upload__notes">
                {document.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}

      {/*
        Its own live region, for the same reason the photo list has one: the
        results region is written to by the check, and whichever text was
        written last would clobber the other.
      */}
      <div
        className="visually-hidden"
        role="status"
        aria-live="polite"
        aria-label="Application form"
      >
        {spoken}
      </div>
    </section>
  )
}
