/**
 * The application, attached rather than typed (FR-11, ADR 0008, US-23, US-24).
 *
 * **This is the primary application-side input on the single-label view**, and
 * it is no longer framed as the alternative to typing. The author's question
 * from using the deployed prototype was when the typed fields would actually be
 * used, and walked through from the agent's chair the answer is: almost never as
 * a starting point. The normal case is an agent holding the COLA document. So
 * the document comes first and the five boxes are a confirmation surface behind
 * a disclosure, which is what `SingleLabelTab` now renders.
 *
 * The values an agent would otherwise type are the values the applicant already
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
import { TileHeading } from './Ui'
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
  /**
   * Called with what the document said and the file it was read from, so the
   * form fields can be filled and, where the document carries its own label
   * artwork, the file can go with the check as the label side (ADR 0010).
   */
  onParsed: (document: ApplicationDocumentResult, file: File) => void
  /** Called when the agent takes the document back off the form. */
  onCleared: () => void
  /**
   * Called when a document was attached and could not be read (FR-9).
   *
   * Distinct from `onCleared`, which is the agent's own deliberate removal.
   * A failed parse is the third case that opens the typed fields: the agent
   * meant to attach the application, the attachment did not work, and the boxes
   * are the fallback. Removing the document is not that, and must not open
   * anything.
   */
  onUnreadable: () => void
}

export function ApplicationUpload({ onParsed, onCleared, onUnreadable }: Props) {
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
      onUnreadable()
      return
    }
    setDocument(outcome.document)
    onParsed(outcome.document, chosen)
    const found = outcome.document.fields.filter((entry) => entry.found_on_document)
    const artwork = found.filter((entry) => entry.source === 'embedded_artwork')
    const artworkSentence = artwork.length
      ? ` ${artwork.map((entry) => entry.display_name).join(', ')} came from the label artwork inside the application rather than from its text.`
      : ''
    setSpoken(
      found.length
        ? `${found.length} of ${outcome.document.fields.length} values filled in from the application form: ${found
            .map((entry) => entry.display_name)
            .join(', ')}.${artworkSentence} Check them and change anything that is wrong.`
        : 'The application form was read, but it did not carry any of the values we compare. Type them in yourself.',
    )
  }

  function clear() {
    void choose(null)
  }

  const found = document?.fields.filter((entry) => entry.found_on_document) ?? []
  const missing = document?.fields.filter((entry) => !entry.found_on_document) ?? []
  // Values that came out of the pictures inside the document rather than out of
  // its text (ADR 0010). Named separately because they are weaker evidence:
  // they went through OCR and can be misread.
  const fromArtwork = found.filter((entry) => entry.source === 'embedded_artwork')

  return (
    <section className="application-upload" aria-labelledby={headingId}>
      <TileHeading glyph="document" tone="gold">
        <h3 className="application-upload__heading" id={headingId}>
          Upload the label application (COLA form)
        </h3>
      </TileHeading>
      <p className="field__hint" id={`${headingId}-hint`}>
        This is what the label is checked against. Attach the applicant&apos;s TTB F 5100.31, or the
        Public COLA Registry printout for it, and we will read what it says. You can change anything
        we get wrong, and you can type the values yourself instead. The file is read here and is not
        sent to TTB or kept.
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
            {document.pages_read > 1 ? ` over ${document.pages_read} pages` : ''}. Open{' '}
            <strong>Or type the application values</strong> below to see them, or to change any of
            them before you run the check.
          </p>
          {fromArtwork.length ? (
            <p className="field__hint">
              {fromArtwork.length === 1
                ? `${fromArtwork[0].display_name} was read from the label artwork inside this application, not from its text.`
                : `${fromArtwork.map((entry) => entry.display_name).join(', ')} were read from the label artwork inside this application, not from its text.`}{' '}
              Those went through the same reading we use on a label photo, so check them.
            </p>
          ) : null}
          {document.label_artwork_available ? (
            <p className="field__hint">
              This application carries its own label artwork, so you do not have to add a photo. We
              will check that artwork. Checking the physical bottle still needs a photo of the
              bottle.
            </p>
          ) : null}
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
