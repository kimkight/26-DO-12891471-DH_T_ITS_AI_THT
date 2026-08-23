/**
 * The batch tab (US-9, US-10, US-11, FR-8, NFR-2).
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
import type { BatchLine } from '../types'

export function BatchTab() {
  const [images, setImages] = useState<File[]>([])
  const [applications, setApplications] = useState<File[]>([])
  const [lines, setLines] = useState<BatchLine[]>([])
  const [total, setTotal] = useState(0)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<UiError | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!images.length || !applications.length || running) return

    const controller = new AbortController()
    abortRef.current = controller
    setRunning(true)
    setError(null)
    setLines([])
    setTotal(0)

    const failure = await verifyBatch(
      images,
      applications[0],
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
        <h2 id="batch-submit-heading">The labels and the application data</h2>

        <form onSubmit={submit} noValidate>
          <DropZone
            label="Label images"
            hint="Drag files here, or choose several at once."
            accept="image/jpeg,image/png,image/webp,image/tiff"
            multiple
            files={images}
            onFiles={setImages}
          />
          <DropZone
            label="Application data file"
            hint="One CSV, with a filename column matching each image."
            accept=".csv,text/csv"
            files={applications}
            onFiles={setApplications}
          />

          <button
            className="button button--primary"
            type="submit"
            disabled={!images.length || !applications.length || running}
          >
            {running ? 'Checking...' : `Check ${images.length || ''} labels`.replace('  ', ' ')}
          </button>
          {running ? (
            <button className="button" type="button" onClick={() => abortRef.current?.abort()}>
              Stop
            </button>
          ) : null}
          {!images.length || !applications.length ? (
            <p className="field__hint">
              Choose the label images and the application data file to turn on the check.
            </p>
          ) : null}
        </form>

        <details className="details">
          <summary>What the application data file needs</summary>
          <p>
            One header row, then one row for each image. The columns are <code>filename</code>,{' '}
            <code>brand_name</code>, <code>class_type</code>, <code>alcohol_content</code>,{' '}
            <code>net_contents</code> and <code>beverage_type</code>. The <code>filename</code> has
            to match the name of one of the images you attached.
          </p>
        </details>
      </section>

      <section className="panel" aria-labelledby="batch-results-heading">
        <h2 id="batch-results-heading">Results</h2>

        <div className="visually-hidden" role="status" aria-live="polite">
          {running
            ? `Checked ${done} of ${total || images.length} labels.`
            : done > 0
              ? `Finished. ${done} labels checked. ${counts.review} need review, ${counts.mismatch} do not match, ${counts.failed} could not be checked.`
              : ''}
        </div>

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

            <button
              className="button"
              type="button"
              onClick={() => downloadCsv(lines)}
              disabled={running}
            >
              Download results CSV
            </button>

            <BatchTable lines={lines} />

            <p className="footnote">
              Nothing here is saved anywhere. Close this page and the results are gone, so download
              the CSV if you need them.
            </p>
          </>
        ) : null}

        {done === 0 && !running && !error ? (
          <p className="placeholder">
            Choose your label images and the application data file, then select
            <strong> Check labels</strong>. Results appear here as each label finishes, so you can
            watch a large batch progress.
          </p>
        ) : null}
      </section>
    </div>
  )
}
