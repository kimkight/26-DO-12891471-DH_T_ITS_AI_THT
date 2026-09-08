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
import { useId, useRef, useState } from 'react'
import { DropZone } from './DropZone'
import { ErrorMessage } from './ErrorMessage'
import { FilePreview, TileHeading } from './Ui'
import { PHOTO_ONLY_NOTE, SIDES, announce } from '../lib/uploadAnnouncement'
import { classifyUploads } from '../lib/api'
import type { UiError } from '../lib/api'
import { pendingFromDocument } from '../lib/pendingArtwork'
import { plainMessage } from '../lib/plainLanguage'
import type { ApplicationDocumentResult, ClassificationResult } from '../types'

/** PDF plus the image types, mirroring what the API accepts on one part. */
export const ACCEPTED_UPLOADS = 'application/pdf,image/jpeg,image/png,image/webp,image/tiff'

/** How each extraction path is described to an agent, in their words. */
const PATHS: Record<ApplicationDocumentResult['extraction_path'], string> = {
  form_fields: 'read from the boxes you filled in on the form',
  embedded_text: 'read from the text in the file',
  ocr: 'read by looking at the pages as pictures, the way we read a label image',
  not_read:
    'because this file has no text to read. Its pages will be read as pictures when you check the label, the way a label image is read',
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
  /** Passed through to the picker, so the reset control can focus it (US-29). */
  pickerRef?: React.RefObject<HTMLInputElement | null>
}

/**
 * One value the form states that the check does not use, as a line.
 *
 * The chip is the whole of the explanation on this screen. Why it is not
 * compared is a question, and questions are answered on the Help tab; here an
 * agent only has to see that we read it and are not using it.
 */
function ValueNote({ label, value }: { label: string; value: string }) {
  return (
    <div className="value-line">
      <span className="value-line__label">{label}</span>
      <span className="value-line__value">{value}</span>
      <span className="chip">Not compared</span>
    </div>
  )
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
  pickerRef,
}: Props) {
  const headingId = useId()
  const [reading, setReading] = useState(false)
  const [result, setResult] = useState<ClassificationResult | null>(null)
  const [error, setError] = useState<UiError | null>(null)
  const [spoken, setSpoken] = useState('')
  /*
   * The classification in flight, and a count of them (code review finding 18,
   * #117). Every change to the list sends the whole list again, so the answer
   * that matters is always the last one sent; an earlier answer arriving late
   * described a list the agent no longer has, and used to fill the boxes and
   * announce a file that had been removed. The controller cancels it; the
   * counter disowns it if it arrives anyway.
   */
  const requestRef = useRef<AbortController | null>(null)
  const requestCount = useRef(0)

  async function send(next: File[]) {
    requestRef.current?.abort()
    const thisRequest = ++requestCount.current
    onFilesChange(next)
    setResult(null)
    setError(null)
    if (!next.length) {
      requestRef.current = null
      setReading(false)
      setSpoken('')
      onCleared()
      return
    }
    const controller = new AbortController()
    requestRef.current = controller
    setReading(true)
    setSpoken('Reading what you uploaded.')
    const outcome = await classifyUploads(next, controller.signal)
    if (outcome.aborted || thisRequest !== requestCount.current) return
    requestRef.current = null
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

  // A value the artwork is about to supply is not a value the agent has to
  // enter (ADR 0017), so it is not listed as one, and neither is any value on
  // a scan whose pages are read by the check (ADR 0024). The check reads the
  // pictures, or the pages, and fills it in.
  const pending = new Set<string>(pendingFromDocument(document))
  const missing =
    document?.fields.filter((entry) => !entry.found_on_document && !pending.has(entry.name)) ?? []

  return (
    <section className="upload-panel" aria-labelledby={headingId}>
      <TileHeading glyph="document" tone="gold">
        <h3 className="upload-panel__heading" id={headingId}>
          Upload the label application, an image of the label, or both
        </h3>
      </TileHeading>
      {/*
        The second sentence of the hint is the advice WCAG 3.2.2 asks for
        before an input changes the context: when an application leaves a
        value unread, focus moves to the box for it (FR-13). Saying so here,
        before the file is chosen, is what makes that move a change the agent
        was told about rather than one that happens to them (code review
        finding 7).
      */}
      <DropZone
        label="Files for this label"
        hint="Drag files here, or choose them: PDF, JPEG, PNG, WebP or TIFF; if the application leaves a value unread, the cursor moves to the box for it."
        accept={ACCEPTED_UPLOADS}
        multiple
        files={[]}
        onFiles={add}
        inputRef={pickerRef}
      />

      {files.length ? (
        <ul className="upload-panel__files">
          {files.map((file, position) => {
            // By position, not by name (code review finding 31): the server
            // reports the files in the order they were sent, which is this
            // list's order, and two files can share a name and differ.
            const entry = result?.files[position]
            return (
              <li className="upload-panel__file" key={`${file.name}-${position}`}>
                {/*
                  A picture is previewed, a PDF is named. The frame carries the
                  filename in its own caption, so naming it twice would be noise
                  on screen and a duplicate for a screen reader. A picture the
                  browser cannot draw, which is every TIFF, gets the frame with
                  an honest placeholder in it rather than a broken image
                  (finding 32; see `FilePreview`).
                */}
                {file.type.startsWith('image/') ? (
                  <FilePreview file={file} />
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

      {/*
        A photograph on its own (code review finding 19, #118). The true thing,
        said once here: it can be checked for what a label must carry, and
        there is nothing to compare it against yet. No box opens and focus
        stays where it was; the same sentence goes to this panel's live region.
      */}
      {result && !document && !result.application_error ? (
        <p className="upload-panel__summary">{PHOTO_ONLY_NOTE}</p>
      ) : null}

      {document ? (
        <div className="upload-panel__result">
          <p className="upload-panel__summary">
            {found.length} of {document.fields.length} values were filled in from the application,{' '}
            {PATHS[document.extraction_path]}
            {document.pages_read > 1 ? ` over ${document.pages_read} pages` : ''}.
          </p>
          {/*
            Two values the form states and the check does not use, as lines
            rather than as sentences (US-28). Each is one row: the name, the
            value, and a chip saying it is not compared. The paragraphs they
            replace explained the same thing in two sentences each, on a screen
            the author said had too many words on it.

            The fanciful name is kept rather than moved to Help entirely, and
            this is the quieter of the two options the brief offered: it is a
            real value the parser read off the document in front of the agent,
            and an agent who wants to know why it is not compared has one place
            to look. The explanation is the Help entry; this is the datum.
          */}
          {document.class_type_code ? (
            <ValueNote label="Class or type code" value={document.class_type_code} />
          ) : null}
          {document.fanciful_name ? (
            <ValueNote label="Fanciful name" value={document.fanciful_name} />
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
