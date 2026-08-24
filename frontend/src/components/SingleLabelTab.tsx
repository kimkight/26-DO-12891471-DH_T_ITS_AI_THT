/**
 * The primary task: check one label (US-1, US-2, US-12, FR-10, NFR-4, NFR-5).
 *
 * NFR-4's first criterion is that "the primary task, verify one label, is
 * reachable from the landing page with no navigation". This is the first tab
 * and it is selected on load, so the form is on screen before anything is
 * clicked. Nothing here is behind a menu, a modal or a second step.
 *
 * The five inputs are the A-14 fields an agent types in (A-8), in the order
 * they appear on a COLA application rather than the order the API returns them.
 * Every one has a `<label>` bound by `htmlFor` (NFR-5's third criterion).
 *
 * None of the five is marked required. FR-2 says a field the application did
 * not supply reads as not compared rather than as a mismatch, so an empty field
 * is a legitimate submission and blocking it in the browser would contradict
 * the requirement the API implements.
 */
import { useRef, useState } from 'react'
import { DropZone } from './DropZone'
import { ErrorMessage } from './ErrorMessage'
import { ResultCard } from './ResultCard'
import { verifyLabel } from '../lib/api'
import type { SingleOutcome } from '../lib/api'
import { announcement } from '../lib/outcomes'
import { EMPTY_APPLICATION } from '../types'
import type { ApplicationData } from '../types'

/** The three classes 27 CFR names. Kept in the words a label reviewer uses. */
const BEVERAGE_TYPES = [
  { value: '', label: 'Choose one' },
  { value: 'distilled spirits', label: 'Distilled spirits' },
  { value: 'wine', label: 'Wine' },
  { value: 'malt beverage', label: 'Malt beverage' },
]

const TEXT_FIELDS: { name: keyof ApplicationData; label: string; hint?: string }[] = [
  { name: 'brand_name', label: 'Brand name' },
  { name: 'class_type', label: 'Class or type designation' },
  { name: 'alcohol_content', label: 'Alcohol content', hint: 'For example 45% or 45' },
  { name: 'net_contents', label: 'Net contents', hint: 'For example 750 mL' },
]

export function SingleLabelTab() {
  const [image, setImage] = useState<File[]>([])
  const [application, setApplication] = useState<ApplicationData>(EMPTY_APPLICATION)
  const [checking, setChecking] = useState(false)
  const [outcome, setOutcome] = useState<SingleOutcome | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  function update(name: keyof ApplicationData, value: string) {
    setApplication((previous) => ({ ...previous, [name]: value }))
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!image.length || checking) return
    setChecking(true)
    setOutcome(null)
    setOutcome(await verifyLabel(image[0], application))
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
        <h2 id="submit-heading">The label and the application</h2>

        <form onSubmit={submit} noValidate>
          <DropZone
            label="Label image"
            hint="Drag a file here, or choose one. JPEG, PNG, WebP or TIFF."
            accept="image/jpeg,image/png,image/webp,image/tiff"
            files={image}
            onFiles={setImage}
          />

          <div className="field">
            <label htmlFor="beverage_type">Beverage type</label>
            <select
              id="beverage_type"
              name="beverage_type"
              value={application.beverage_type}
              onChange={(event) => update('beverage_type', event.target.value)}
            >
              {BEVERAGE_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {TEXT_FIELDS.map((field) => (
            <div className="field" key={field.name}>
              <label htmlFor={field.name}>{field.label}</label>
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
                aria-describedby={field.hint ? `${field.name}-hint` : undefined}
                value={application[field.name]}
                onChange={(event) => update(field.name, event.target.value)}
              />
            </div>
          ))}

          <button className="button button--primary" type="submit" disabled={!image.length}>
            {checking ? 'Checking...' : 'Check this label'}
          </button>
          {!image.length ? (
            <p className="field__hint">Choose a label image to turn on the check.</p>
          ) : null}
        </form>
      </section>

      <section className="panel" aria-labelledby="results-heading" ref={resultsRef}>
        <h2 id="results-heading">What we found</h2>

        {/*
          NFR-5's last criterion: results appearing after submission are
          announced to assistive technology. Polite rather than assertive, so
          it waits for the agent to finish what they are reading. It is always
          in the DOM, never conditionally mounted, because a live region added
          at the same moment as its text is not reliably announced.
        */}
        <div className="visually-hidden" role="status" aria-live="polite">
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
            <div className="cards">
              {result.fields.map((field) => (
                <ResultCard key={field.name} field={field} warning={result.warning_detail} />
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
            Choose a label image, fill in what the application says, and select
            <strong> Check this label</strong>. The five results appear here.
          </p>
        ) : null}
      </section>
    </div>
  )
}
