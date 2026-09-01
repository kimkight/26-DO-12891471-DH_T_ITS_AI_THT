/**
 * The primary task: check one label (US-1, US-2, US-12, US-22, FR-10, NFR-4,
 * NFR-5, ADR 0007).
 *
 * NFR-4's first criterion is that "the primary task, verify one label, is
 * reachable from the landing page with no navigation". This is the first tab
 * and it is selected on load, so the form is on screen before anything is
 * clicked. Nothing here is behind a menu, a modal or a second step.
 *
 * **The application document comes first, and the typed fields are behind a
 * disclosure (US-24).** The author's question, from using the deployed
 * prototype, was when the typed fields would actually be used. Walked through
 * from the agent's chair the answer is: almost never as a starting point. The
 * normal case is that the agent is holding the COLA document, and then the five
 * boxes are a confirmation surface rather than a data-entry task. The layout
 * used to say the opposite, greeting the agent with five empty text boxes and
 * styling the upload as the alternative, so it is inverted: upload, then check,
 * with the boxes behind a disclosure.
 *
 * The typed fields open in exactly three cases, and never close themselves:
 *
 * 1. The agent opens the disclosure. No document at hand, reading the values
 *    off another screen.
 * 2. A parsed document leaves gaps. The form proper carries no class or type,
 *    alcohol content or net contents boxes (A-17), so gaps are the normal
 *    outcome rather than an error, though the artwork embedded in the document
 *    may now close them (ADR 0010); the fields appear with the parsed values
 *    filled and the gaps empty.
 * 3. A document fails to parse. FR-9's message names the problem and the fields
 *    open as the fallback.
 *
 * A document that fills everything opens nothing: the upload's own summary says
 * what it read, and an agent who wants to see or change it opens the
 * disclosure. Auto-expansion is announced to a live region of its own, and
 * never moves focus, because the agent may be reading something else when the
 * parse returns.
 *
 * The five inputs are the fields an agent would otherwise type (A-8), in the
 * order they appear on a COLA application rather than the order the API
 * returns them. Every one has a `<label>` bound by `htmlFor` (NFR-5's third
 * criterion).
 *
 * None of the five is marked required. FR-2 says a field the application did
 * not supply reads as not compared rather than as a mismatch, so an empty field
 * is a legitimate submission and blocking it in the browser would contradict
 * the requirement the API implements.
 *
 * **One upload, for everything (FR-12, ADR 0011).** There is one file picker.
 * It takes the label application, photographs of the label, or any mix, as PDFs
 * or images, and the server decides what each file is from the file rather than
 * from which control it arrived in. Two pickers asked the agent to sort their
 * own files before the tool had looked at them, and an agent who guessed wrong
 * got a COLA form read as label artwork. The classification comes back per file
 * and is shown, so a wrong one is visible rather than silent.
 *
 * The check turns on as soon as anything is uploaded. Three submissions are
 * valid and all three complete: the application alone, where its own embedded
 * artwork is the label side (ADR 0010); a photograph plus typed values; or
 * both. An application with no readable artwork and no photograph is refused
 * with a message naming the missing piece, which is an FR-9 message rather than
 * a validation error on a field.
 *
 * **More than one photograph of the same label (ADR 0007) still applies.** A
 * label wraps a round bottle, so no single photograph shows all of it flat, and
 * up to TTB_MAX_LABEL_PHOTOS pictures of one label are still read independently
 * and merged. What has gone is the row of numbered slots: an agent adds files
 * and the server counts them. It is one label throughout: one set of
 * application values, one result, one set of five field cards. The batch tab is
 * still the place for many different labels.
 *
 * **The application, uploaded rather than typed (FR-11, ADR 0008).** The five
 * values are the values the applicant already submitted on TTB F 5100.31, so
 * the form is the way they arrive. What comes back fills these same fields and
 * is marked as read from the application form; the fields stay editable, and
 * the check runs on whatever is in them when the button is pressed. FR-11's
 * precedence is unchanged: a typed value always wins. Editing a filled field
 * clears its mark, because it is the agent's value from that point on.
 * Uploading is not the COLA integration OOS-1 excludes: the document is read
 * locally and nothing reaches TTB.
 *
 * **The screen says what happened and stops (2026-08-31).** The author, on the
 * released build: "I don't need the time listed on the screen think about what a
 * regular application looks like do not put all these extra words on the screen
 * that should not be there." So the timing line and the phase disclosure are
 * gone from the panel. The phases are still measured and still in the API
 * response, where the deployment runbook reads them; what has gone is the tool
 * talking about itself in the middle of somebody's work. Every notice is said
 * once, where it is first relevant, rather than in the upload card and the
 * results header and every affected row. `quietScreen.test.tsx` holds the
 * budget.
 *
 * **Beverage type is demoted rather than removed.** It is never compared, and
 * no per-field comparison reads it: A-12's proof cross-check keys off a proof
 * statement the label itself carries and A-13's range handling keys off a range
 * in the value, so an unstated beverage type costs the comparison nothing. It
 * fills from the document when the document states it, sits at the bottom of
 * the disclosure otherwise, and the rule that ran is named in the result's own
 * reason line rather than inferred from this control.
 */
import { useState } from 'react'
import { ApplicationFields } from './ApplicationFields'
import { ErrorMessage } from './ErrorMessage'
import { PhotoNotes } from './PhotoNotes'
import { ResultCard } from './ResultCard'
import { Kicker } from './Ui'
import { UploadPanel } from './UploadPanel'
import { verifyLabel } from '../lib/api'
import type { SingleOutcome } from '../lib/api'
import { typedValues } from '../lib/applicationFields'
import type { SourceMap } from '../lib/applicationFields'
import { ARTWORK_LABEL_LINE, documentSource } from '../lib/applicationSources'
import { PRESENCE_LIMIT, anySearched } from '../lib/labelSearch'
import { announcement, summary } from '../lib/outcomes'
import { pendingFromArtwork } from '../lib/pendingArtwork'
import { EMPTY_APPLICATION } from '../types'
import type { ApplicationData, ApplicationDocumentResult, ClassificationResult } from '../types'

/**
 * Keep only the values the agent typed themselves.
 *
 * Used when the document goes away: what an agent typed is still theirs, and
 * what a document supplied is no longer attributable to anything, so it stops
 * claiming a source it no longer has.
 */
/**
 * The five application-side values, in the order the interface shows them.
 *
 * The four compared ones plus the beverage type, which is never compared and
 * is why it is last (A-12, A-13).
 */
const APPLICATION_FIELDS: (keyof ApplicationData)[] = [
  'brand_name',
  'class_type',
  'alcohol_content',
  'net_contents',
  'beverage_type',
]

function onlyTyped(previous: SourceMap, application: ApplicationData): SourceMap {
  const next: SourceMap = {}
  for (const [name, source] of Object.entries(previous) as [
    keyof ApplicationData,
    SourceMap[keyof ApplicationData],
  ][]) {
    if (source === 'typed' && application[name].trim()) next[name] = 'typed'
  }
  return next
}

export function SingleLabelTab() {
  // Everything the agent uploaded for this label, in the order they chose it.
  // One list, not two: what each file is, is the server's judgement (FR-12).
  const [files, setFiles] = useState<File[]>([])
  const [application, setApplication] = useState<ApplicationData>(EMPTY_APPLICATION)
  /*
   * Where each value came from (ADR 0010, ADR 0011). A map rather than the set
   * of "read from the form" names it replaces, because there are now three
   * document-side sources and an agent looking at a prefilled field is entitled
   * to know which one they are looking at: a value read out of a text layer
   * cannot be misread, and a value recognized off a picture can.
   */
  const [sources, setSources] = useState<SourceMap>({})
  /*
   * Whether anything has been uploaded and read yet. It is what separates the
   * two layouts: before it, the Session 10 disclosure over five empty boxes;
   * after it, summary lines for what was read and visible fields for what was
   * not (US-26).
   */
  const [processed, setProcessed] = useState(false)
  /*
   * Which values the upload did not supply. Decided when the upload is read and
   * not recomputed as the agent types, because a field that moved between the
   * two sections mid-edit would remount under them and drop focus.
   */
  const [gaps, setGaps] = useState<(keyof ApplicationData)[]>([])
  /*
   * The values the check will read off the artwork (ADR 0017). Neither read nor
   * missing: the prefill pass counted the pictures and left them, so there is
   * nothing to summarise and nothing to ask for.
   */
  const [pending, setPending] = useState<(keyof ApplicationData)[]>([])
  // The disclosure. Collapsed on load; opened by the agent, or by a document
  // that failed to parse, and never closed by anything but the agent.
  const [fieldsOpen, setFieldsOpen] = useState(false)
  const [fieldsNews, setFieldsNews] = useState('')
  const [checking, setChecking] = useState(false)
  const [outcome, setOutcome] = useState<SingleOutcome | null>(null)

  function update(name: keyof ApplicationData, value: string) {
    setApplication((previous) => ({ ...previous, [name]: value }))
    // The agent has taken this field over. The source becomes theirs, so the
    // interface never tells them a value came off a document when it did not.
    setSources((previous) => ({ ...previous, [name]: value.trim() ? 'typed' : 'absent' }))
  }

  /**
   * Fill the fields from what the server read off the uploaded application.
   *
   * Called with the whole classification, because a submission carrying only
   * label pictures found no application at all and still counts as processed:
   * the fields section has to stop showing five empty boxes either way.
   */
  function fillFromClassification(result: ClassificationResult) {
    setProcessed(true)
    if (!result.application_document) {
      // Nothing on the application side: a label picture and nothing else. What
      // the agent typed stays theirs; everything they did not type is a gap,
      // because nothing supplied it.
      setSources((previous) => onlyTyped(previous, application))
      setGaps(APPLICATION_FIELDS.filter((name) => !application[name].trim()))
      setPending([])
      return
    }
    fillFromDocument(result.application_document)
  }

  /**
   * Write what the document said into the fields it answers (FR-11).
   *
   * Every value the document supplied is written into its field, including over
   * something already typed there: uploading the application is a deliberate
   * act and the agent is asking for what it says. Nothing is lost that cannot
   * be typed back, every value stays editable, and the source is recorded per
   * field so the interface can say where each one came from.
   */
  function fillFromDocument(document: ApplicationDocumentResult) {
    const filled = document.fields.filter((entry) => entry.found_on_document)
    setApplication((previous) => {
      const next = { ...previous }
      for (const entry of filled) {
        if (entry.name in next && entry.value) {
          next[entry.name as keyof ApplicationData] = entry.value
        }
      }
      return next
    })
    setSources(() => {
      const next: SourceMap = {}
      for (const entry of document.fields) {
        next[entry.name as keyof ApplicationData] = entry.found_on_document
          ? documentSource(entry.source)
          : 'absent'
      }
      return next
    })

    // A gap is a compared value neither the document nor the agent supplied.
    // Something already typed is not a gap: the agent answered it.
    //
    // Nor is a value the artwork is about to supply (ADR 0017). The prefill
    // pass reads the document's text layer and leaves the pictures to the
    // check, so alcohol content and net contents are commonly still to come
    // rather than absent. Opening a box and moving focus into it for a value
    // the next click fills in would be the tool asking the agent to do its own
    // work, one second before doing it.
    const supplied = new Set(
      filled.map((entry) => entry.name).filter((name) => name in EMPTY_APPLICATION),
    )
    const owed = pendingFromArtwork(document)
    const stillComing = new Set(owed)
    setPending(owed.filter((name) => !application[name].trim()))
    setGaps(
      APPLICATION_FIELDS.filter(
        (name) => !supplied.has(name) && !stillComing.has(name) && !application[name].trim(),
      ),
    )
  }

  /** Taking every file back off returns the view to its unprocessed state. */
  function clearFormMarks() {
    setSources((previous) => onlyTyped(previous, application))
    setProcessed(false)
    setGaps([])
    setPending([])
  }

  /**
   * A document was uploaded and could not be read (FR-9).
   *
   * The agent meant to supply the application and it did not arrive, so the
   * boxes open as the fallback the error message promises. The error itself is
   * rendered and announced by `UploadPanel`; this only says that the fields are
   * now open, so the two live regions do not say the same thing twice.
   */
  function openFieldsAfterFailure() {
    setSources((previous) => onlyTyped(previous, application))
    setProcessed(false)
    setGaps([])
    setPending([])
    setFieldsOpen(true)
    setFieldsNews('The application values are open below so you can type them in yourself.')
  }

  function toggleFields() {
    // The button's own aria-expanded announces this one, so the live region is
    // cleared rather than written to: an agent who pressed the control does not
    // need to be told twice that it worked.
    setFieldsNews('')
    setFieldsOpen((open) => !open)
  }

  /*
   * There is something to check as soon as anything has been uploaded. The
   * label image requirement is gone as a hard gate (FR-12): the author's words
   * on 2026-08-29 were "if COLA is uploaded, I don't also need an image".
   *
   * What cannot be checked is decided by the server, which has read the files,
   * and reported as an FR-9 message naming the missing piece. Guessing at it
   * here would mean this component classifying files it has not read, which is
   * the thing FR-12 removes.
   */
  const canCheck = files.length > 0

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!canCheck || checking) return
    setChecking(true)
    setOutcome(null)
    // What the agent typed, and nothing the interface filled in from the
    // document (FR-14). See `typedValues` for what posting the rest back does
    // to a document-only submission.
    setOutcome(await verifyLabel(files, typedValues(application, sources)))
    setChecking(false)
  }

  const result = outcome?.result ?? null
  // The live region text. Empty while checking so that the "Checking" line and
  // the result are not both announced as one run-on sentence.
  const spoken = result ? announcement(result.fields.map((field) => field.outcome)) : ''

  return (
    <div className="layout">
      <section className="panel" aria-labelledby="submit-heading">
        <Kicker glyph="label">Label check</Kicker>
        {/*
          The heading names three things this interface actually performs.
          It used to read "Point. Upload. Check.", inherited from a pattern
          built for a phone camera; there is no camera here and nothing is
          pointed at anything, so the first verb promised a capability the
          tool does not have (US-27).
        */}
        <h2 id="submit-heading">Upload. Read. Check.</h2>

        <form onSubmit={submit} noValidate>
          <UploadPanel
            files={files}
            onFilesChange={setFiles}
            onClassified={fillFromClassification}
            onCleared={clearFormMarks}
            onUnreadable={openFieldsAfterFailure}
          />

          <ApplicationFields
            application={application}
            sources={sources}
            processed={processed}
            gaps={gaps}
            pending={pending}
            open={fieldsOpen}
            onToggle={toggleFields}
            onChange={update}
            onGapNews={setFieldsNews}
          />

          {/*
            Its own region, for the same reason the uploads have one. It carries
            what the fields section has to say for itself: which value was not
            read and what to do about it, or that the boxes were opened as the
            fallback after a document failed to parse.
          */}
          <div
            className="visually-hidden"
            role="status"
            aria-live="polite"
            aria-label="Application values"
          >
            {fieldsNews}
          </div>

          <button className="button button--primary" type="submit" disabled={!canCheck}>
            {checking ? 'Checking...' : 'Check this label'}
          </button>
          {!canCheck ? (
            <p className="field__hint">
              Upload something to turn on the check: the label application, an image of the label,
              or both.
            </p>
          ) : null}
        </form>
      </section>

      <section className="panel" aria-labelledby="results-heading">
        <Kicker glyph="document" tone="navy">
          Field by field
        </Kicker>
        <h2 id="results-heading">What we found</h2>

        {/*
          NFR-5's last criterion: results appearing after submission are
          announced to assistive technology. Polite rather than assertive, so
          it waits for the agent to finish what they are reading. It is always
          in the DOM, never conditionally mounted, because a live region added
          at the same moment as its text is not reliably announced.
        */}
        <div className="visually-hidden" role="status" aria-live="polite" aria-label="Check result">
          {checking ? 'Checking this label.' : spoken}
        </div>

        {outcome?.error ? <ErrorMessage error={outcome.error} /> : null}

        {result ? (
          <>
            {/*
              The summary line, and the reason it is not "5 of 5 fields match"
              (FR-14, ADR 0013). Where some of the five rows compared a value
              against the artwork it was read from, saying five would count
              fields that could not have come out any other way. The line says
              what is true instead: how many of the verifiable ones match, and
              how many were only read.
            */}
            <p className="summary-line">{summary(result.fields.map((field) => field.outcome))}</p>
            {/*
              The limit of what a search establishes, said once (ADR 0015). Each
              row that was decided by searching says where on the label the
              declared value was found; this says what that does and does not
              prove. Once, above the rows, rather than on each of them.
            */}
            {anySearched(result.fields.map((field) => field.reason)) ? (
              <p className="footnote footnote--search">{PRESENCE_LIMIT}</p>
            ) : null}
            {result.label_source === 'application_artwork' ? (
              <p className="footnote footnote--artwork">{ARTWORK_LABEL_LINE}</p>
            ) : null}
            <PhotoNotes photos={result.photos} />
            <div className="cards">
              {result.fields.map((field) => (
                <ResultCard
                  key={field.name}
                  field={field}
                  warning={result.warning_detail}
                  photoCount={result.photos.length}
                />
              ))}
            </div>
            <p className="footnote">This tool recommends. You decide.</p>
          </>
        ) : null}

        {!result && !outcome?.error && !checking ? (
          <p className="placeholder">
            Upload the label application, an image of the label, or both, then select
            <strong> Check this label</strong>. The five results appear here. Nothing to upload for
            the application side? Open <strong>Or type the application values</strong> and type them
            instead.
          </p>
        ) : null}
      </section>
    </div>
  )
}
