/**
 * The batch tab (US-9, US-10, US-11, US-23, FR-8, FR-11, NFR-2).
 *
 * **A batch is label images plus COLA documents, paired by filename stem**
 * (ADR 0009). `0001-stones-throw.png` goes with `0001-stones-throw.pdf`. It was
 * images plus one CSV of application data until assumption A-14 was superseded:
 * no source ever stated that format, and what an importer actually files is,
 * per application, a COLA form plus label images.
 *
 * The pairing rule is stated on the page, and the pairing itself is worked out
 * here as soon as files are chosen, before anything is sent. An agent who has
 * dropped 300 images and 299 documents should find that out from the page
 * rather than from one error line 20 minutes into a run. The same sentence goes
 * to the live region, so it reaches a screen reader without being read twice
 * (NFR-5).
 *
 * NFR-2's second criterion is that "batch progress is observable to the user
 * rather than presenting as a frozen page". The stream carries a position and a
 * total on every line, so the progress bar is driven by what has actually
 * finished rather than by an animation that would keep moving if the server
 * stopped.
 *
 * Rows are appended as they arrive. A batch that fails halfway keeps every row
 * it received, because discarding completed work is the failure NFR-2 names.
 */
import { useRef, useState } from 'react'
import { BatchTable } from './BatchTable'
import { DropZone } from './DropZone'
import { ErrorMessage } from './ErrorMessage'
import { verifyBatch } from '../lib/api'
import type { UiError } from '../lib/api'
import { rowOutcome } from '../lib/outcomes'
import { downloadCsv } from '../lib/csv'
import { describePairing, pair } from '../lib/pairing'
import { Chip, Kicker } from './Ui'
import type { BatchLine } from '../types'

export function BatchTab() {
  const [images, setImages] = useState<File[]>([])
  const [documents, setDocuments] = useState<File[]>([])
  const [lines, setLines] = useState<BatchLine[]>([])
  const [total, setTotal] = useState(0)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<UiError | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!images.length || !documents.length || running) return

    const controller = new AbortController()
    abortRef.current = controller
    setRunning(true)
    setError(null)
    setLines([])
    setTotal(0)

    const failure = await verifyBatch(
      images,
      documents,
      (line) => {
        setTotal(line.total)
        setLines((previous) => [...previous, line])
      },
      controller.signal,
    )

    setError(failure)
    setRunning(false)
    abortRef.current = null
  }

  const pairing = pair(images, documents)
  const chosen = images.length > 0 || documents.length > 0
  const pairingSentence = describePairing(pairing)

  const done = lines.length
  const counts = {
    checked: lines.filter((line) => rowOutcome(line) === 'match').length,
    review: lines.filter((line) => rowOutcome(line) === 'needs_review').length,
    mismatch: lines.filter((line) => rowOutcome(line) === 'mismatch').length,
    failed: lines.filter((line) => rowOutcome(line) === 'error').length,
  }

  return (
    <div className="layout">
      <section className="panel" aria-labelledby="batch-submit-heading">
        <Kicker glyph="stack">Bulk submission</Kicker>
        <h2 id="batch-submit-heading">Many labels, checked one by one.</h2>

        {/*
          The pairing rule, stated before the controls rather than hidden in a
          disclosure, because it is what the agent has to do to their filenames
          before they can use this page at all.
        */}
        <p className="field__hint" id="batch-pairing-rule">
          Attach the label images and one COLA document for each. They are matched by name: a
          document named <code>0001-stones-throw.pdf</code> goes with the image named{' '}
          <code>0001-stones-throw.png</code>. Only the file extension may differ, and upper and
          lower case do not matter.
        </p>

        <form onSubmit={submit} noValidate>
          <DropZone
            label="Label images"
            hint="Drag files here, or choose several at once. One image for each label."
            accept="image/jpeg,image/png,image/webp,image/tiff"
            multiple
            files={images}
            onFiles={setImages}
          />
          <DropZone
            label="COLA documents"
            hint="One for each label image, named to match it. A PDF, or a scan or photograph of the form."
            accept="application/pdf,image/jpeg,image/png,image/webp,image/tiff"
            multiple
            files={documents}
            onFiles={setDocuments}
          />

          {/*
            Announced as well as shown, from the same sentence, so a screen
            reader user learns what a sighted agent learns from the counts.
            `role="status"` rather than an alert: this is the state of the
            submission, not an error to clear.
          */}
          {chosen ? (
            <p className="field__hint" role="status" aria-live="polite">
              <Chip tone="navy" dot>
                {pairingSentence}
              </Chip>
            </p>
          ) : null}

          {pairing.imagesWithoutDocument.length || pairing.documentsWithoutImage.length ? (
            <details className="details">
              <summary>Which files are unmatched</summary>
              {pairing.imagesWithoutDocument.length ? (
                <p>
                  No document matches: {pairing.imagesWithoutDocument.join(', ')}. You can still run
                  the check; each of these reports an error on its own line and the rest of the
                  batch is unaffected.
                </p>
              ) : null}
              {pairing.documentsWithoutImage.length ? (
                <p>No image matches: {pairing.documentsWithoutImage.join(', ')}.</p>
              ) : null}
              {pairing.ambiguous.length ? (
                <p>
                  Used more than once, so which document belongs to which label is ambiguous:{' '}
                  {pairing.ambiguous.join(', ')}.
                </p>
              ) : null}
            </details>
          ) : null}

          <button
            className="button button--primary"
            type="submit"
            disabled={!images.length || !documents.length || running}
          >
            {running ? 'Checking...' : `Check ${images.length || ''} labels`.replace('  ', ' ')}
          </button>
          {running ? (
            <button className="button" type="button" onClick={() => abortRef.current?.abort()}>
              Stop
            </button>
          ) : null}
          {!images.length || !documents.length ? (
            <p className="field__hint">
              Choose the label images and their COLA documents to turn on the check.
            </p>
          ) : null}
        </form>

        <details className="details">
          <summary>What the COLA documents are read for</summary>
          <p>
            Each document supplies the application side of its label: the brand name, the class or
            type designation, the alcohol content and the net contents. It is read here, on this
            server, with no call to the COLA system. A value the document does not carry is reported
            as not found for that label rather than guessed, and the field is not compared.
          </p>
        </details>
      </section>

      <section className="panel" aria-labelledby="batch-results-heading">
        <Kicker glyph="check" tone="navy">
          {running ? 'Reading' : 'Results'}
        </Kicker>
        <h2 id="batch-results-heading">Results</h2>

        <div className="visually-hidden" role="status" aria-live="polite">
          {running
            ? `Checked ${done} of ${total || images.length} labels.`
            : done > 0
              ? `Finished. ${done} labels checked. ${counts.review} need review, ${counts.mismatch} do not match, ${counts.failed} could not be checked.`
              : ''}
        </div>

        {/*
          The reading line, while the stream is open. Decoration over the live
          region below it, which says the same thing to a screen reader and is
          unchanged; the dots are aria-hidden and stop moving for anyone who has
          asked for reduced motion.
        */}
        {running ? (
          <p className="reading-line">
            <span className="reading-line__pulse" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
            Reading label {Math.min(done + 1, total || images.length)} of {total || images.length}
            ...
          </p>
        ) : null}

        {(running || done > 0) && total > 0 ? (
          <div className="progress">
            {/*
              A real <progress> element rather than a styled div, so its value
              and maximum are exposed without any ARIA of our own. The visible
              count beside it is what an agent reads; the element is what a
              screen reader reads.
            */}
            <progress id="batch-progress" max={total} value={done} />
            <label htmlFor="batch-progress">
              {done} of {total} labels checked
            </label>
          </div>
        ) : null}

        {error ? <ErrorMessage error={error} /> : null}

        {done > 0 ? (
          <>
            {/*
              Noun phrases rather than verbs, so the line reads correctly at
              every count. "1 need your review" is wrong and "1 needs your
              review" would need pluralisation logic for no gain.
            */}
            <ul className="summary">
              <li>
                <strong>{counts.checked}</strong> fully matching
              </li>
              <li>
                <strong>{counts.review}</strong> needing review
              </li>
              <li>
                <strong>{counts.mismatch}</strong> not matching
              </li>
              <li>
                <strong>{counts.failed}</strong> could not be checked
              </li>
            </ul>

            <BatchTable lines={lines} />

            {/*
              The running total, pinned under the rows. It is the one line an
              agent watches while a 300-label batch runs, so it is set apart
              from the four per-outcome counts above rather than being a fifth
              of them. Not a live region: the polite one above already
              announces the same progress, and two regions saying it would make
              a screen reader read every row twice.
            */}
            <p className="total-row">
              <span className="total-row__label">Running total</span>
              <span className="total-row__value">
                {done} of {total || done} checked, {counts.mismatch}{' '}
                {counts.mismatch === 1 ? 'mismatch' : 'mismatches'}
              </span>
            </p>

            <button
              className="button"
              type="button"
              onClick={() => downloadCsv(lines)}
              disabled={running}
            >
              Download results CSV
            </button>

            <p className="footnote">
              Nothing here is saved anywhere. Close this page and the results are gone, so download
              the CSV if you need them.
            </p>
          </>
        ) : null}

        {done === 0 && !running && !error ? (
          <p className="placeholder">
            Choose your label images and their COLA documents, then select
            <strong> Check labels</strong>. Results appear here as each label finishes, so you can
            watch a large batch progress.
          </p>
        ) : null}
      </section>
    </div>
  )
}
