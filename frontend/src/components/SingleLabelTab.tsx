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
 * styling the upload as the alternative, so it is inverted: photos, then the
 * application, then check.
 *
 * The typed fields open in exactly three cases, and never close themselves:
 *
 * 1. The agent opens the disclosure. No document at hand, reading the values
 *    off another screen.
 * 2. A parsed document leaves gaps. The form proper carries no class or type,
 *    alcohol content or net contents boxes (A-17), so gaps are the normal
 *    outcome rather than an error; the fields appear with the parsed values
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
 * **More than one photograph of the same label (ADR 0007).** A label wraps a
 * round bottle, so no single photograph shows all of it flat. The form starts
 * with one photo slot, which is the case almost every check will be, and an
 * agent who needs a second or a third adds them one at a time. It is one label
 * throughout: one set of application values, one result, one set of five field
 * cards. The batch tab is still the place for many different labels.
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
 * **Beverage type is demoted rather than removed.** It is never compared, and
 * no per-field comparison reads it: A-12's proof cross-check keys off a proof
 * statement the label itself carries and A-13's range handling keys off a range
 * in the value, so an unstated beverage type costs the comparison nothing. It
 * fills from the document when the document states it, sits at the bottom of
 * the disclosure otherwise, and the rule that ran is named in the result's own
 * reason line rather than inferred from this control.
 */
import { useEffect, useRef, useState } from 'react'
import { ApplicationUpload } from './ApplicationUpload'
import { DropZone } from './DropZone'
import { ErrorMessage } from './ErrorMessage'
import { PhotoNotes } from './PhotoNotes'
import { ResultCard } from './ResultCard'
import { Chip, Kicker } from './Ui'
import { verifyLabel } from '../lib/api'
import type { SingleOutcome } from '../lib/api'
import { ARTWORK_LABEL_LINE } from '../lib/applicationSources'
import { announcement } from '../lib/outcomes'
import { EMPTY_APPLICATION } from '../types'
import type { ApplicationData, ApplicationDocumentResult } from '../types'

/**
 * The mark on a field whose value was read off the uploaded application.
 *
 * Text rather than colour alone, and bound to the input through
 * `aria-describedby`, so it reaches a screen reader and survives greyscale
 * (NFR-5). It says "change it if it is wrong" because an agent who cannot tell
 * whether they are allowed to edit a filled field will not edit it.
 */
function FromFormMark({ name }: { name: string }) {
  return (
    <p className="field__source" id={`${name}-from-form`}>
      Read from the application form. Change it if it is wrong.
    </p>
  )
}

/**
 * Join names the way a sentence does, so the announcement reads as English
 * rather than as a comma-separated list. Used only in the live region, where a
 * screen reader speaks the punctuation it is given.
 */
function names(items: string[]): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

/** The three classes 27 CFR names. Kept in the words a label reviewer uses. */
const BEVERAGE_TYPES = [
  { value: '', label: 'Choose one' },
  { value: 'distilled spirits', label: 'Distilled spirits' },
  { value: 'wine', label: 'Wine' },
  { value: 'malt beverage', label: 'Malt beverage' },
]

/**
 * The id of the panel the disclosure controls. A constant rather than `useId`
 * because it is referenced from `aria-controls` and from the toggle in the same
 * component, and a stable string is easier to read in a failing test.
 */
const TYPED_FIELDS_PANEL = 'typed-application-values'

const TEXT_FIELDS: { name: keyof ApplicationData; label: string; hint?: string }[] = [
  { name: 'brand_name', label: 'Brand name' },
  { name: 'class_type', label: 'Class or type designation' },
  { name: 'alcohol_content', label: 'Alcohol content', hint: 'For example 45% or 45' },
  { name: 'net_contents', label: 'Net contents', hint: 'For example 750 mL' },
]

/**
 * Mirrors TTB_MAX_LABEL_PHOTOS. The API refuses more than this and names the
 * limit; this stops an agent reaching that refusal by hiding the control that
 * would cause it, which is the shape NFR-4 asks for.
 */
const MAX_PHOTOS = 3

const ACCEPTED = 'image/jpeg,image/png,image/webp,image/tiff'

export function SingleLabelTab() {
  // One slot per photograph, in submission order. `null` is an empty slot: an
  // added slot exists before a file is chosen for it, so the drop zone has
  // somewhere to be.
  const [slots, setSlots] = useState<(File | null)[]>([null])
  const [slotNews, setSlotNews] = useState('')
  const [application, setApplication] = useState<ApplicationData>(EMPTY_APPLICATION)
  // Which fields currently hold a value read off an uploaded application, so
  // each one can say so. A field the agent then edits leaves this set.
  const [fromForm, setFromForm] = useState<Set<keyof ApplicationData>>(new Set())
  // The disclosure over the typed fields. Collapsed on load; opened by the
  // agent, or by one of the two document cases below, and never closed by
  // anything but the agent.
  const [fieldsOpen, setFieldsOpen] = useState(false)
  /*
   * The attached application, when it carries label artwork of its own
   * (ADR 0010). Held here rather than in `ApplicationUpload` because it is the
   * label side of the check when no photograph was taken, and the check is
   * submitted from here.
   */
  const [artworkDocument, setArtworkDocument] = useState<File | null>(null)
  const [fieldsNews, setFieldsNews] = useState('')
  const [checking, setChecking] = useState(false)
  const [outcome, setOutcome] = useState<SingleOutcome | null>(null)
  const addRef = useRef<HTMLButtonElement>(null)
  /*
   * Put focus back on "Add another photo of this label" after a slot is
   * removed. It has to happen after the render rather than in the click
   * handler: removing the third slot is what brings that button back into the
   * DOM, so at the moment of the click the ref is still null and focus would
   * fall to the document body, which is where a keyboard user loses their
   * place.
   *
   * A ref rather than state for the flag, and cleared before the focus call.
   * State would mean a second render whose only purpose is to unset a boolean
   * nothing renders, which is the cascading-render shape React warns about.
   */
  const returnFocusToAdd = useRef(false)
  useEffect(() => {
    if (!returnFocusToAdd.current) return
    returnFocusToAdd.current = false
    addRef.current?.focus()
  }, [slots.length])

  const photos = slots.filter((file): file is File => file !== null)

  function update(name: keyof ApplicationData, value: string) {
    setApplication((previous) => ({ ...previous, [name]: value }))
    // The agent has taken this field over. The mark goes, so the interface
    // never tells them a value came off the form when it did not.
    setFromForm((previous) => {
      if (!previous.has(name)) return previous
      const next = new Set(previous)
      next.delete(name)
      return next
    })
  }

  /**
   * Fill the fields from an uploaded application (FR-11).
   *
   * Every value the document supplied is written into its field, including over
   * something already typed there: attaching the form is a deliberate act and
   * the agent is asking for what it says. Nothing is lost that cannot be typed
   * back, every field stays editable, and the live region in ApplicationUpload
   * names what was filled.
   */
  function fillFromDocument(document: ApplicationDocumentResult, file: File) {
    setArtworkDocument(document.label_artwork_available ? file : null)
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
    setFromForm(new Set(filled.map((entry) => entry.name as keyof ApplicationData)))

    /*
     * The second auto-expansion case: the document was read and left gaps.
     * Gaps are normal rather than exceptional, because the form proper carries
     * no class or type, alcohol content or net contents boxes at all (A-17),
     * so this is the common path for a real TTB F 5100.31 and the rare one for
     * a Registry printout. The fields open with the parsed values in place and
     * the gaps empty, so the agent sees exactly what is left to do.
     */
    const gaps = document.fields.filter((entry) => !entry.found_on_document)
    if (!gaps.length) return
    setFieldsOpen(true)
    setFieldsNews(
      `The application values are open below, because this form did not carry ${names(
        gaps.map((entry) => entry.display_name.toLowerCase()),
      )}. What it did carry is already filled in.`,
    )
  }

  /** Taking the document back off the form clears only the marks, not the values. */
  function clearFormMarks() {
    setFromForm(new Set())
    setArtworkDocument(null)
  }

  /**
   * The third auto-expansion case: a document was attached and could not be
   * read (FR-9). The agent meant to supply the application and it did not
   * arrive, so the boxes open as the fallback the error message promises. The
   * error itself is rendered and announced by `ApplicationUpload`; this only
   * says that the fields are now open, so the two live regions do not say the
   * same thing twice.
   */
  function openFieldsAfterFailure() {
    setFromForm(new Set())
    setArtworkDocument(null)
    setFieldsOpen(true)
    setFieldsNews('The application values are open below so you can type them in yourself.')
  }

  /** The first auto-expansion case, and the only one that can also close. */
  function toggleFields() {
    // The button's own aria-expanded announces this one, so the live region is
    // cleared rather than written to: an agent who pressed the control does not
    // need to be told twice that it worked.
    setFieldsNews('')
    setFieldsOpen((open) => !open)
  }

  function setSlot(position: number, file: File | null) {
    setSlots((previous) => previous.map((slot, index) => (index === position ? file : slot)))
  }

  function addSlot() {
    if (slots.length >= MAX_PHOTOS) return
    const next = slots.length + 1
    setSlots((previous) => [...previous, null])
    setSlotNews(
      next === MAX_PHOTOS
        ? `Photo ${next} added. That is the most photos you can add for one label.`
        : `Photo ${next} added. You can add ${MAX_PHOTOS - next} more.`,
    )
  }

  function removeSlot(position: number) {
    setSlots((previous) => previous.filter((_, index) => index !== position))
    const remaining = slots.length - 1
    setSlotNews(
      `Photo ${position + 1} removed. ${remaining} photo${remaining === 1 ? '' : 's'} left.`,
    )
    returnFocusToAdd.current = true
  }

  /*
   * There is something to check when the agent took a photograph, or when the
   * application they attached carries its own label artwork (ADR 0010). The
   * author's words on 2026-08-29: "if COLA is uploaded, I don't also need an
   * image."
   */
  const canCheck = photos.length > 0 || artworkDocument !== null

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!canCheck || checking) return
    setChecking(true)
    setOutcome(null)
    setOutcome(await verifyLabel(photos, application, artworkDocument))
    setChecking(false)
  }

  const result = outcome?.result ?? null
  // The live region text. Empty while checking so that the "Checking" line and
  // the result are not both announced as one run-on sentence.
  const spoken = result
    ? announcement(
        result.fields.map((field) => field.outcome),
        outcome?.seconds ?? 0,
      )
    : ''

  return (
    <div className="layout">
      <section className="panel" aria-labelledby="submit-heading">
        <Kicker glyph="scan">Label scanning</Kicker>
        <h2 id="submit-heading">Point. Upload. Check.</h2>

        <form onSubmit={submit} noValidate>
          <fieldset className="photos">
            <legend className="photos__legend">
              Photos of this label{' '}
              <span className="photos__count">
                <Chip>
                  {photos.length} of {MAX_PHOTOS} chosen
                </Chip>
              </span>
            </legend>
            <p className="field__hint" id="photos-hint">
              One photo is usually enough. A label wraps around the bottle, so add a second or a
              third if one photo cannot show all of it.
            </p>

            {slots.map((file, position) => (
              <div className="photos__slot" key={position}>
                <DropZone
                  label={position === 0 ? 'Label image' : `Label image, photo ${position + 1}`}
                  hint="Drag a file here, or choose one. JPEG, PNG, WebP or TIFF."
                  accept={ACCEPTED}
                  preview
                  files={file ? [file] : []}
                  onFiles={(chosen) => setSlot(position, chosen[0] ?? null)}
                />
                {position > 0 ? (
                  <button
                    className="button button--quiet"
                    type="button"
                    onClick={() => removeSlot(position)}
                  >
                    Remove photo {position + 1}
                  </button>
                ) : null}
              </div>
            ))}

            {slots.length < MAX_PHOTOS ? (
              <button
                ref={addRef}
                className="button button--quiet"
                type="button"
                onClick={addSlot}
                aria-describedby="photos-hint"
              >
                Add another photo of this label
              </button>
            ) : (
              <p className="field__hint">
                That is the most photos you can add for one label. Remove one to add a different
                one.
              </p>
            )}

            {/*
              Adding and removing a slot changes the form without moving focus
              anywhere that announces it, so the change is spoken here. Its own
              region rather than the results one, which would be clobbered by
              whichever text was written last.
            */}
            <div
              className="visually-hidden"
              role="status"
              aria-live="polite"
              aria-label="Photo list"
            >
              {slotNews}
            </div>
          </fieldset>

          <ApplicationUpload
            onParsed={fillFromDocument}
            onCleared={clearFormMarks}
            onUnreadable={openFieldsAfterFailure}
          />

          {/*
            The typed values, behind a disclosure (US-24). A button with
            aria-expanded and aria-controls rather than <details>, because the
            open state has to be settable from the two document cases as well as
            from the control, and a controlled native disclosure is harder to
            reason about than an explicit one.

            The panel keeps its contents in the DOM when collapsed and hides
            them with the `hidden` attribute, so the fields leave the tab order
            and the accessibility tree together rather than one without the
            other.
          */}
          <div className="disclosure">
            <button
              className="button button--quiet disclosure__toggle"
              type="button"
              aria-expanded={fieldsOpen}
              aria-controls={TYPED_FIELDS_PANEL}
              onClick={toggleFields}
            >
              <span className="disclosure__marker" aria-hidden="true" />
              Or type the application values
            </button>

            <div className="disclosure__panel" id={TYPED_FIELDS_PANEL} hidden={!fieldsOpen}>
              <p className="field__hint">
                The check runs on whatever is in these boxes. A value you type here is used instead
                of the one read off the application. Leave a box empty and that field is not
                compared.
              </p>

              {TEXT_FIELDS.map((field) => {
                const marked = fromForm.has(field.name)
                const describedBy = [
                  field.hint ? `${field.name}-hint` : null,
                  marked ? `${field.name}-from-form` : null,
                ]
                  .filter(Boolean)
                  .join(' ')
                return (
                  <div className="field" key={field.name}>
                    <label htmlFor={field.name}>{field.label}</label>
                    {marked ? <FromFormMark name={field.name} /> : null}
                    {field.hint ? (
                      <p className="field__hint" id={`${field.name}-hint`}>
                        {field.hint}
                      </p>
                    ) : null}
                    <input
                      id={field.name}
                      name={field.name}
                      type="text"
                      autoComplete="off"
                      aria-describedby={describedBy || undefined}
                      value={application[field.name]}
                      onChange={(event) => update(field.name, event.target.value)}
                    />
                  </div>
                )
              })}

              {/*
                Last, and no longer the first field an agent meets. It is never
                compared: it only says which numeric rule to expect, and the
                result's own reason line names the rule that actually ran.
              */}
              <div className="field">
                <label htmlFor="beverage_type">Beverage type</label>
                {fromForm.has('beverage_type') ? <FromFormMark name="beverage_type" /> : null}
                <p className="field__hint" id="beverage_type-hint">
                  Not compared against the label. It says which numeric rule to expect: the proof
                  cross-check for spirits, range handling for wine.
                </p>
                <select
                  id="beverage_type"
                  name="beverage_type"
                  value={application.beverage_type}
                  aria-describedby={
                    fromForm.has('beverage_type')
                      ? 'beverage_type-hint beverage_type-from-form'
                      : 'beverage_type-hint'
                  }
                  onChange={(event) => update('beverage_type', event.target.value)}
                >
                  {BEVERAGE_TYPES.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/*
              Its own region, for the same reason the photo list has one. It is
              written to only when something other than the agent opened the
              panel, because the button's aria-expanded already reports the
              agent's own press.
            */}
            <div
              className="visually-hidden"
              role="status"
              aria-live="polite"
              aria-label="Application values"
            >
              {fieldsNews}
            </div>
          </div>

          <button className="button button--primary" type="submit" disabled={!canCheck}>
            {checking ? 'Checking...' : 'Check this label'}
          </button>
          {!canCheck ? (
            <p className="field__hint">
              Choose a label image, or attach an application that carries the label artwork, to turn
              on the check.
            </p>
          ) : null}
          {!photos.length && artworkDocument ? (
            <p className="field__hint">
              We will check the label artwork inside the application you attached. Add a photo if
              you want to check a bottle instead.
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
            <p className="timing">
              Checked in {outcome!.seconds.toFixed(1)} seconds.{' '}
              <span className="timing__detail">
                {result.elapsed_ms.toFixed(0)} ms of that was inside the checker, the rest was
                sending the image and receiving the answer.
              </span>
            </p>
            {/*
              One short line, once, when the label being checked came out of the
              application document rather than off a bottle (ADR 0010). It is
              the honest limitation, stated where the agent is reading the
              result rather than left to a document.
            */}
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
            <p className="footnote">
              This tool recommends. You decide. Every value it read off the label is shown beside
              the value on the application so you can check the call rather than take it.
            </p>
          </>
        ) : null}

        {!result && !outcome?.error && !checking ? (
          <p className="placeholder">
            Take your photos, attach the label application, and select
            <strong> Check this label</strong>. The five results appear here. No application to
            attach? Open <strong>Or type the application values</strong> and type them instead.
          </p>
        ) : null}
      </section>
    </div>
  )
}
