/**
 * One upload, for everything (FR-12, ADR 0011, US-25).
 *
 * The author's words on 2026-08-29, after the deployed build refused to check a
 * COLA document because a label image was also required: "if COLA is uploaded,
 * I don't also need an image", and "these should be combined; just one upload;
 * simplify the interface. You should be able to upload (pdfs or images)."
 *
 * So there is one file picker. It takes PDFs and images, one file or several,
 * in any mix, and **the server decides what each file is from the file itself**
 * rather than from which control it arrived in. That is the part worth stating:
 * two pickers asked the agent to classify their own files before the tool had
 * looked at them, and an agent who guessed wrong got a COLA form read as label
 * artwork. The classification comes back per file and is shown, so a wrong one
 * is visible rather than silent.
 *
 * **What this replaces.** The photo slots from ADR 0007 and the separate
 * application upload from ADR 0008. Both of those still exist underneath: up to
 * TTB_MAX_LABEL_PHOTOS pictures of one label are still merged, and the
 * application is still read locally with no call to TTB. What has gone is the
 * agent having to say in advance which is which.
 *
 * **Accessibility.** One labelled control, a real `<input type="file">` with a
 * `<label>` bound to it, so it is keyboard reachable and announced as a file
 * input by anything that already knows what one is. Drag and drop is added on
 * top and nothing depends on it. Each accepted file is announced to this
 * panel's own live region together with what it was taken to be, because an
 * agent who cannot see the list has no other way to learn that their COLA form
 * was read as a label.
 */
import { useId, useState } from 'react'
import { DropZone } from './DropZone'
import { ErrorMessage } from './ErrorMessage'
import { ScanFrame, TileHeading } from './Ui'
import { SIDES, announce } from '../lib/uploadAnnouncement'
import { classifyUploads } from '../lib/api'
import type { UiError } from '../lib/api'
import { plainMessage } from '../lib/plainLanguage'
import type { ApplicationDocumentResult, ClassificationResult } from '../types'

/** PDF plus the image types, mirroring what the API accepts on one part. */
export const ACCEPTED_UPLOADS = 'application/pdf,image/jpeg,image/png,image/webp,image/tiff'

/** How each extraction path is described to an agent, in their words. */
const PATHS: Record<ApplicationDocumentResult['extraction_path'], string> = {
  form_fields: 'read from the boxes you filled in on the form',
  embedded_text: 'read from the text in the file',
  ocr: 'read by looking at the pages as pictures, the way we read a label photo',
}

interface Props {
  /** The files currently chosen, held by the parent because it submits them. */
  files: File[]
  /** Called whenever the list changes, before the classification comes back. */
  onFilesChange: (files: File[]) => void
  /** Called with the server's sorting and, where there was one, the application. */
  onClassified: (result: ClassificationResult) => void
  /** Called when a file classified as the application could not be read (FR-9). */
  onUnreadable: () => void
  /** Called when the last file is taken back off. */
  onCleared: () => void
}

/** Two files are the same file when their name, size and modified time agree. */
function sameFile(one: File, other: File): boolean {
  return (
    one.name === other.name && one.size === other.size && one.lastModified === other.lastModified
  )
}

export function UploadPanel({
  files,
  onFilesChange,
  onClassified,
  onUnreadable,
  onCleared,
}: Props) {
  const headingId = useId()
  const [reading, setReading] = useState(false)
  const [result, setResult] = useState<ClassificationResult | null>(null)
  const [error, setError] = useState<UiError | null>(null)
  const [spoken, setSpoken] = useState('')

  async function send(next: File[]) {
    onFilesChange(next)
    setResult(null)
    setError(null)
    if (!next.length) {
      setSpoken('')
      onCleared()
      return
    }
    setReading(true)
    setSpoken('Reading what you uploaded.')
    const outcome = await classifyUploads(next)
    setReading(false)
    if (outcome.error || !outcome.result) {
      setError(outcome.error)
      setSpoken(outcome.error?.message ?? '')
      return
    }
    setResult(outcome.result)
    onClassified(outcome.result)
    setSpoken(announce(outcome.result))
    if (outcome.result.application_error) onUnreadable()
  }

  function add(chosen: File[]) {
    // Added rather than replacing, because an agent choosing a second file
    // means "and this one too". Duplicates are dropped so that choosing the
    // same file twice does not submit it twice.
    const next = [...files]
    for (const file of chosen) {
      if (!next.some((existing) => sameFile(existing, file))) next.push(file)
    }
    void send(next)
  }

  function remove(position: number) {
    void send(files.filter((_, index) => index !== position))
  }

  const document = result?.application_document ?? null
  const found = document?.fields.filter((entry) => entry.found_on_document) ?? []
  const missing = document?.fields.filter((entry) => !entry.found_on_document) ?? []
  const fromArtwork = found.filter((entry) => entry.source === 'embedded_artwork')

  return (
    <section className="upload-panel" aria-labelledby={headingId}>
      <TileHeading glyph="document" tone="gold">
        <h3 className="upload-panel__heading" id={headingId}>
          Upload the label application, a photo of the label, or both
        </h3>
      </TileHeading>
      <p className="field__hint" id={`${headingId}-hint`}>
        One place for everything. PDFs and photos, one file or several. We work out what each one
        is: an application tells us what the label should say, a photo shows us what it does say. An
        application that carries its own label artwork is enough on its own. Files are read here and
        are not sent to TTB or kept.
      </p>

      <DropZone
        label="Files for this label"
        hint="Drag files here, or choose them. PDF, JPEG, PNG, WebP or TIFF."
        accept={ACCEPTED_UPLOADS}
        multiple
        files={[]}
        onFiles={add}
      />

      {files.length ? (
        <ul className="upload-panel__files">
          {files.map((file, position) => {
            const entry = result?.files.find((item) => item.filename === file.name)
            return (
              <li className="upload-panel__file" key={`${file.name}-${position}`}>
                {/*
                  A picture is previewed, a PDF is named. The frame carries the
                  filename in its own caption, so naming it twice would be noise
                  on screen and a duplicate for a screen reader.
                */}
                {file.type.startsWith('image/') ? (
                  <ScanFrame file={file} />
                ) : (
                  <span className="upload-panel__name">{file.name}</span>
                )}
                {entry ? (
                  <span
                    className={`chip chip--${entry.classified_as === 'application_document' ? 'gold' : 'navy'}`}
                  >
                    {SIDES[entry.classified_as]}
                  </span>
                ) : (
                  <span className="chip">Reading...</span>
                )}
                {entry ? <span className="upload-panel__reason">{entry.reason}</span> : null}
                {entry && !entry.used ? (
                  <span className="upload-panel__reason">
                    Not used: only one application is read for one label.
                  </span>
                ) : null}
                <button
                  className="button button--quiet"
                  type="button"
                  onClick={() => remove(position)}
                >
                  Remove {file.name}
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}

      {reading ? <p className="field__hint">Reading what you uploaded...</p> : null}
      {error ? <ErrorMessage error={error} /> : null}
      {/*
        The classification stands and the file is still listed as the label
        application; what failed is reading it (FR-9). It goes through the same
        plain-language mapping every other failure does, with the API's own
        message kept underneath as the detail.
      */}
      {result?.application_error ? (
        <ErrorMessage
          error={{
            message: plainMessage(result.application_error.code),
            detail: result.application_error.message,
          }}
        />
      ) : null}

      {document ? (
        <div className="upload-panel__result">
          <p className="upload-panel__summary">
            {found.length} of {document.fields.length} values were filled in from the application,{' '}
            {PATHS[document.extraction_path]}
            {document.pages_read > 1 ? ` over ${document.pages_read} pages` : ''}.
          </p>
          {fromArtwork.length ? (
            <p className="field__hint">
              {fromArtwork.map((entry) => entry.display_name).join(', ')}{' '}
              {fromArtwork.length === 1 ? 'was' : 'were'} read from the label artwork inside this
              application, not from its text. Those went through the same reading we use on a label
              photo, so check them.
            </p>
          ) : null}
          {document.label_artwork_available && !result?.label_images ? (
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
              <p className="upload-panel__summary">
                Not on this application, so you will need to enter{' '}
                {missing.map((entry) => entry.display_name.toLowerCase()).join(', ')}:
              </p>
              <ul className="upload-panel__notes">
                {document.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            </>
          ) : null}
        </div>
      ) : null}

      {/*
        Its own live region. The results region is written to by the check, and
        whichever text was written last would clobber the other.
      */}
      <div className="visually-hidden" role="status" aria-live="polite" aria-label="Your uploads">
        {spoken}
      </div>
    </section>
  )
}
