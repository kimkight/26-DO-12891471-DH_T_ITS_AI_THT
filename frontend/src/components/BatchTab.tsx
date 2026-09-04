/**
 * The batch tab (US-9, US-10, US-11, US-23, FR-8, FR-11, FR-12, NFR-2, NFR-5).
 *
 * **The same tool as the single-label tab, for many labels at once**
 * (ADR 0020). The author, on the v1.2.1 build: "I need for the functionality
 * of that page to mimic the check on label page. It should also accept the
 * COLA application, pdf or images (with a single choose file; not 2). The
 * results should be to the right but in table format in a list."
 *
 * So there is one file control, taking PDFs and images together, and every
 * file is classified on arrival with the same call the single-label tab makes;
 * the queue shows what each was taken to be in the same chip. Files that share
 * a name before the extension are one label, and the grouping is derived here
 * by the server's own rule so the table can lay out one row per label before
 * the batch is sent. Nothing is demanded of the names: a filed application
 * that carries its own artwork is a complete label on its own, a photograph
 * on its own is checked for what a label must carry, and a file that could not
 * be read becomes a visible row rather than an absence.
 *
 * The results are one table on the right, one row per label in the order
 * submitted, each filling in as its line arrives. Selecting a row opens the
 * field-by-field detail in the component the single-label tab renders.
 *
 * **What it used to be.** Two pickers, "Label images" and "COLA documents",
 * paired by filename stem and inert until both were chosen (ADR 0009). That
 * required an image for every label when a filed application carries its own,
 * asked the agent to sort files the server could sort, and showed results in
 * a vocabulary of its own. ADR 0020 records what that model assumed.
 *
 * NFR-2's second criterion is that "batch progress is observable to the user
 * rather than presenting as a frozen page". The stream carries a position and a
 * total on every line, so the progress bar is driven by what has actually
 * finished rather than by an animation that would keep moving if the server
 * stopped. Rows are kept as they arrive: a batch that fails halfway keeps every
 * row it received, because discarding completed work is the failure NFR-2
 * names.
 */
import { useEffect, useId, useRef, useState } from 'react'
import { BatchTable } from './BatchTable'
import type { BatchRow } from './BatchTable'
import { DropZone } from './DropZone'
import { ErrorMessage } from './ErrorMessage'
import { ResultDetail } from './ResultDetail'
import { Chip, Kicker } from './Ui'
import { ACCEPTED_UPLOADS } from './UploadPanel'
import { classifyUploads, verifyBatch } from '../lib/api'
import type { UiError } from '../lib/api'
import { downloadCsv } from '../lib/csv'
import { ROW_BUCKETS, rowOutcome } from '../lib/outcomes'
import { describeGroups, groupByStem, groupShape } from '../lib/pairing'
import type { KnownSide } from '../lib/pairing'
import { plainMessage } from '../lib/plainLanguage'
import { SIDES } from '../lib/uploadAnnouncement'
import type { BatchLine, FileClassification } from '../types'

/** One file in the queue, and what the server has said about it so far. */
interface QueuedFile {
  /** Stable across reorders and removals; a name is not, since two files can share one. */
  id: number
  file: File
  /**
   * `provisional` is an image the page has not sent for sorting (OQ-37). It
   * is shown as a label image until the batch runs, and the chip says so.
   */
  state: 'reading' | 'sorted' | 'failed' | 'provisional'
  classification?: FileClassification
  error?: UiError
}

/**
 * Whether a file is sorted on arrival, or sorted when the batch runs (OQ-37).
 *
 * A PDF is sorted from its header and its text layer, which costs under fifty
 * milliseconds a file. An image has no text layer: deciding whether it is a
 * photographed form or a label is a full OCR pass, the same pass the check
 * makes a moment later in a different request, and measured at about 2.3 s a
 * file on the deployed task. Twenty photographs cost 23 s of "Reading..."
 * before the batch had started, and the check then read every one again. A
 * server-side cache of that read is what NFR-6 forbids. So an image is not
 * sent: it is shown as a label image, provisionally and labelled as such,
 * and the batch line replaces the chip with what the server actually decided.
 * A photographed form is still sorted correctly; it is sorted when checked.
 */
function sortedOnArrival(file: File): boolean {
  return file.type === 'application/pdf' || /\.pdf$/i.test(file.name)
}

/** The provisional chip's text and reason, until the batch line arrives. */
export const PROVISIONAL_SIDE = 'Label image, sorted when checked'
export const PROVISIONAL_REASON =
  'Pictures are sorted when the batch runs, so the batch does not read each one twice. ' +
  'A photographed application is still read as one then.'

/**
 * How many classification requests are in flight at once.
 *
 * Every file is sent on its own rather than the whole list on every change,
 * because a batch can be 300 files and the classify route's envelope is the
 * single-label one. Two at a time keeps the chips arriving while the agent is
 * still dropping files, without turning a 300-file drop into 300 concurrent
 * requests against a server whose OCR runs behind a one-worker limiter.
 */
const CLASSIFY_IN_FLIGHT = 2

function sideOf(entry: QueuedFile): KnownSide {
  if (entry.state === 'reading') return null
  if (entry.state === 'failed') return 'failed'
  if (entry.state === 'provisional') return 'label_image'
  return entry.classification?.classified_as ?? 'failed'
}

export function BatchTab() {
  const [queue, setQueue] = useState<QueuedFile[]>([])
  const [lines, setLines] = useState<Record<number, BatchLine>>({})
  const [total, setTotal] = useState(0)
  const [running, setRunning] = useState(false)
  const [started, setStarted] = useState(false)
  const [error, setError] = useState<UiError | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  /*
   * A remount key for the picker (US-29). The batch view holds state, so it
   * gets a reset like the single-label view; the picker is remounted for the
   * same reason the single-label one is, because a file input's own value is
   * not React's to clear and an agent choosing the same file again has to get
   * an event.
   */
  const [generation, setGeneration] = useState(0)
  const [cleared, setCleared] = useState('')
  const abortRef = useRef<AbortController | null>(null)
  const pickerRef = useRef<HTMLInputElement>(null)
  const detailId = useId()
  const detailHeadingId = useId()

  /*
   * The classification queue (finding 18's shape, per file). Each file's
   * request has its own controller so removing the file, or resetting, cancels
   * it, and a set of live ids is what stops an answer for a removed file from
   * landing anyway. Refs rather than state, because the scheduler runs from
   * promise callbacks and must see the current picture, not a render's.
   */
  const nextId = useRef(0)
  const live = useRef(new Set<number>())
  const waiting = useRef<QueuedFile[]>([])
  const inFlight = useRef(new Map<number, AbortController>())

  function pump() {
    while (inFlight.current.size < CLASSIFY_IN_FLIGHT && waiting.current.length) {
      const entry = waiting.current.shift()!
      if (!live.current.has(entry.id)) continue
      const controller = new AbortController()
      inFlight.current.set(entry.id, controller)
      void classifyUploads([entry.file], controller.signal).then((outcome) => {
        inFlight.current.delete(entry.id)
        if (!outcome.aborted && live.current.has(entry.id)) {
          setQueue((previous) =>
            previous.map((queued) => {
              if (queued.id !== entry.id) return queued
              const sorted = outcome.result?.files[0]
              return sorted
                ? { ...queued, state: 'sorted', classification: sorted }
                : { ...queued, state: 'failed', error: outcome.error ?? undefined }
            }),
          )
        }
        pump()
      })
    }
  }

  function add(chosen: File[]) {
    // Added rather than replacing, because an agent choosing a second batch of
    // files means "and these too". Duplicates are dropped so that choosing the
    // same file twice does not submit it twice.
    const additions: QueuedFile[] = []
    for (const file of chosen) {
      if (queue.some((queued) => sameFile(queued.file, file))) continue
      if (additions.some((queued) => sameFile(queued.file, file))) continue
      const deferred = !sortedOnArrival(file)
      const entry: QueuedFile = {
        id: nextId.current++,
        file,
        state: deferred ? 'provisional' : 'reading',
      }
      additions.push(entry)
      live.current.add(entry.id)
      if (!deferred) waiting.current.push(entry)
    }
    if (!additions.length) return
    setQueue((previous) => [...previous, ...additions])
    setCleared('')
    pump()
  }

  function remove(id: number) {
    live.current.delete(id)
    inFlight.current.get(id)?.abort()
    inFlight.current.delete(id)
    waiting.current = waiting.current.filter((entry) => entry.id !== id)
    setQueue((previous) => previous.filter((entry) => entry.id !== id))
    pump()
  }

  /**
   * Clear the batch and go back to the empty state (US-29).
   *
   * Stops a running stream first, and every classification still in flight
   * (code review finding 17). A reset that left one open would keep appending
   * rows to a table the agent has just emptied, which is the one way this
   * control could do something worse than nothing.
   *
   * No confirmation, for the reason the single-label one has none: nothing is
   * stored, and the CSV button beside it is how results leave this page.
   */
  function reset() {
    abortRef.current?.abort()
    abortRef.current = null
    for (const controller of inFlight.current.values()) controller.abort()
    inFlight.current.clear()
    waiting.current = []
    live.current.clear()
    setQueue([])
    setLines({})
    setTotal(0)
    setRunning(false)
    setStarted(false)
    setError(null)
    setSelected(null)
    setCleared('The batch was cleared. Choose the next set of files.')
    setGeneration((previous) => previous + 1)
  }

  useEffect(() => {
    if (generation === 0) return
    pickerRef.current?.focus()
  }, [generation])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    if (!queue.length || running) return

    const controller = new AbortController()
    abortRef.current = controller
    setRunning(true)
    setStarted(true)
    setError(null)
    setLines({})
    setTotal(0)
    setSelected(null)
    setCleared('')

    const failure = await verifyBatch(
      queue.map((entry) => entry.file),
      (line) => {
        setTotal(line.total)
        setLines((previous) => ({ ...previous, [line.position]: line }))
        // The server's own sorting replaces a provisional chip (OQ-37): the
        // line carries what each file in the row was taken to be.
        const sorted = line.result?.files ?? []
        if (sorted.length) {
          setQueue((previous) =>
            previous.map((queued) => {
              if (queued.state !== 'provisional') return queued
              const entry = sorted.find((file) => file.filename === queued.file.name)
              return entry ? { ...queued, state: 'sorted', classification: entry } : queued
            }),
          )
        }
      },
      controller.signal,
    )

    // A reset while this ran has already cleared the screen, and this answer
    // is about a batch that no longer exists (finding 17). Stop is different:
    // the agent ended the run and keeps what arrived, so the screen settles.
    if (abortRef.current !== controller) return
    setError(failure)
    setRunning(false)
    abortRef.current = null
  }

  // The rows, grouped by the server's own rule, so the table exists before
  // the batch runs and every line has a row to land in (ADR 0020).
  const groups = groupByStem(queue.map((entry) => entry.file.name))
  const shapes = groups.map((group) =>
    groupShape(group.indexes.map((index) => sideOf(queue[index]))),
  )
  const rows: BatchRow[] = groups.map((group) => {
    const members = group.indexes.map((index) => queue[index])
    const line = lines[group.position] ?? null
    const image = members.find((entry) => entry.classification?.classified_as === 'label_image')
    return {
      position: group.position,
      name: line?.filename ?? image?.file.name ?? members[0].file.name,
      files: members.map((entry) => entry.file.name),
      line,
    }
  })
  // A line for a row the page did not predict (the server is the authority on
  // the grouping) is still shown rather than dropped.
  for (const line of Object.values(lines)) {
    if (!rows.some((row) => row.position === line.position)) {
      rows.push({
        position: line.position,
        name: line.filename ?? `Label ${line.position}`,
        files: line.filenames,
        line,
      })
    }
  }
  rows.sort((one, other) => one.position - other.position)

  const groupsSentence = describeGroups(shapes)
  const canCheck = queue.length > 0
  const clearable = queue.length > 0 || started || error !== null

  const done = Object.keys(lines).length
  const received = Object.values(lines)
  /*
   * One count per bucket, over the same `rowOutcome` the chip uses, so the
   * seven counts sum to the row count (code review finding 16, #115). The
   * finished sentence names only the buckets that are not zero, because a
   * screen reader user should not sit through four zeroes to reach the one
   * number that matters.
   */
  const tally = ROW_BUCKETS.map((bucket) => ({
    ...bucket,
    count: received.filter((line) => rowOutcome(line) === bucket.outcome).length,
  }))
  const counts = Object.fromEntries(
    tally.map((bucket) => [bucket.outcome, bucket.count]),
  ) as Record<(typeof ROW_BUCKETS)[number]['outcome'], number>
  const finished = tally
    .filter((bucket) => bucket.count > 0)
    .map((bucket) => `${bucket.count} ${bucket.label}`)
    .join(', ')
  const expected = total || rows.length

  const open = selected === null ? null : (rows.find((row) => row.position === selected) ?? null)

  return (
    <div className="layout">
      <section className="panel" aria-labelledby="batch-submit-heading">
        <Kicker glyph="stack">Bulk submission</Kicker>
        <h2 id="batch-submit-heading">Many labels, checked one by one.</h2>

        <form onSubmit={submit} noValidate>
          <DropZone
            key={generation}
            inputRef={pickerRef}
            label="Files for these labels"
            hint="Drag files here, or choose them: PDF, JPEG, PNG, WebP or TIFF, applications and label images together. Files with the same name before the extension are one label."
            accept={ACCEPTED_UPLOADS}
            multiple
            files={[]}
            onFiles={add}
          />

          {queue.length ? (
            <ul className="upload-panel__files" aria-label="Files in this batch">
              {queue.map((entry) => (
                <li className="upload-panel__file" key={entry.id}>
                  <span className="upload-panel__name">{entry.file.name}</span>
                  {/*
                    The same chip the single-label tab puts beside a file, from
                    the same classification (FR-12). A file the server could
                    not sort says so here and becomes an error row when the
                    batch runs, rather than disappearing from either.
                  */}
                  {entry.state === 'sorted' && entry.classification ? (
                    <span
                      className={`chip chip--${entry.classification.classified_as === 'application_document' ? 'gold' : 'navy'}`}
                    >
                      {SIDES[entry.classification.classified_as]}
                    </span>
                  ) : entry.state === 'failed' ? (
                    <span className="chip">Could not be read</span>
                  ) : entry.state === 'provisional' ? (
                    <span className="chip chip--navy">{PROVISIONAL_SIDE}</span>
                  ) : (
                    <span className="chip">Reading...</span>
                  )}
                  {entry.classification ? (
                    <span className="upload-panel__reason">{entry.classification.reason}</span>
                  ) : entry.error ? (
                    <span className="upload-panel__reason">{entry.error.message}</span>
                  ) : entry.state === 'provisional' ? (
                    <span className="upload-panel__reason">{PROVISIONAL_REASON}</span>
                  ) : null}
                  <button
                    className="button button--quiet"
                    type="button"
                    onClick={() => remove(entry.id)}
                  >
                    Remove {entry.file.name}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}

          {/*
            Announced as well as shown, from the same sentence, so a screen
            reader user learns what a sighted agent learns from the list.
            `role="status"` rather than an alert: this is the state of the
            submission, not an error to clear. Always in the DOM and labelled
            (4.1.3); the name is kept from v1.3.0 so nothing that finds the
            region by it has to change.
          */}
          <p className="field__hint" role="status" aria-live="polite" aria-label="Batch pairing">
            {groupsSentence ? (
              <Chip tone="navy" dot>
                {groupsSentence}
              </Chip>
            ) : null}
          </p>

          <button className="button button--primary" type="submit" disabled={!canCheck || running}>
            {running
              ? 'Checking...'
              : `Check ${rows.length || ''} ${rows.length === 1 ? 'label' : 'labels'}`.replace(
                  '  ',
                  ' ',
                )}
          </button>
          {running ? (
            <button className="button" type="button" onClick={() => abortRef.current?.abort()}>
              Stop
            </button>
          ) : null}
          {/*
            The same short label the single-label tab shows (US-28): the reason
            the button is inert is one word long, and what it takes is a
            question for the Help tab.
          */}
          {!canCheck ? <p className="field__hint">Upload a file to check.</p> : null}
        </form>
      </section>

      <section className="panel" aria-labelledby="batch-results-heading">
        <Kicker glyph="check" tone="navy">
          {running ? 'Reading' : 'Results'}
        </Kicker>
        <h2 id="batch-results-heading">Results</h2>

        <div
          className="visually-hidden"
          role="status"
          aria-live="polite"
          aria-label="Batch progress"
        >
          {running
            ? `Checked ${done} of ${expected} labels.`
            : done > 0
              ? `Finished. ${done} labels checked: ${finished}.`
              : cleared}
        </div>

        {/*
          The reading line, while the stream is open. Decoration over the live
          region above it, which says the same thing to a screen reader and is
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
            Reading label {Math.min(done + 1, expected)} of {expected}...
          </p>
        ) : null}

        {started && expected > 0 ? (
          <div className="progress">
            {/*
              A real <progress> element rather than a styled div, so its value
              and maximum are exposed without any ARIA of our own. The visible
              count beside it is what an agent reads; the element is what a
              screen reader reads.
            */}
            <progress id="batch-progress" max={expected} value={done} />
            <label htmlFor="batch-progress">
              {done} of {expected} labels checked
            </label>
          </div>
        ) : null}

        {error ? <ErrorMessage error={error} /> : null}

        {started ? (
          <>
            {/*
              Noun phrases rather than verbs, so the line reads correctly at
              every count. "1 need your review" is wrong and "1 needs your
              review" would need pluralisation logic for no gain.
            */}
            <ul className="summary">
              {tally.map((bucket) => (
                <li key={bucket.outcome}>
                  <strong>{bucket.count}</strong> {bucket.label}
                </li>
              ))}
            </ul>

            <BatchTable
              rows={rows}
              running={running}
              selected={selected}
              onSelect={setSelected}
              detailId={detailId}
            />

            {/*
              The detail for the selected row, in the same component the
              single-label tab renders (ADR 0020). It is always in the DOM so
              the row buttons' aria-controls points at something; hidden when
              no row is open, which takes it out of the accessibility tree
              and the tab order together.
            */}
            <section
              id={detailId}
              className="batch-detail"
              aria-labelledby={detailHeadingId}
              hidden={open === null}
            >
              {open ? (
                <>
                  <h3 className="batch-detail__heading" id={detailHeadingId}>
                    Label {open.position} of {expected}: {open.name}
                  </h3>
                  <ul className="batch-detail__files" aria-label="Files for this label">
                    {(open.line?.result?.files?.length
                      ? open.line.result.files.map((entry) => ({
                          name: entry.filename,
                          side: entry.classified_as as KnownSide,
                        }))
                      : open.files.map((name) => {
                          const queued = queue.find((entry) => entry.file.name === name)
                          return { name, side: queued ? sideOf(queued) : null }
                        })
                    ).map((entry, at) => (
                      <li key={`${entry.name}-${at}`}>
                        <span className="upload-panel__name">{entry.name}</span>{' '}
                        {entry.side === 'application_document' || entry.side === 'label_image' ? (
                          <span
                            className={`chip chip--${entry.side === 'application_document' ? 'gold' : 'navy'}`}
                          >
                            {SIDES[entry.side]}
                          </span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                  {open.line?.result ? (
                    <ResultDetail result={open.line.result} idPrefix="batch-card" />
                  ) : open.line?.error ? (
                    <ErrorMessage
                      error={{
                        message: rowMessage(open.line),
                        detail: [open.line.error.message, open.line.error.limit]
                          .filter(Boolean)
                          .join(' '),
                      }}
                    />
                  ) : running ? (
                    <p className="field__hint">Still reading this label.</p>
                  ) : (
                    <p className="field__hint">
                      No result arrived for this label. The batch stopped before it was reached; run
                      it again, or check the label on its own.
                    </p>
                  )}
                </>
              ) : null}
            </section>

            {/*
              The running total, pinned under the rows. It is the one line an
              agent watches while a 300-label batch runs, so it is set apart
              from the per-outcome counts above rather than being one of them.
              Not a live region: the polite one above already announces the
              same progress, and two regions saying it would make a screen
              reader read every row twice.
            */}
            <p className="total-row">
              <span className="total-row__label">Running total</span>
              <span className="total-row__value">
                {done} of {expected} checked, {counts.mismatch}{' '}
                {counts.mismatch === 1 ? 'mismatch' : 'mismatches'}
              </span>
            </p>

            <button
              className="button"
              type="button"
              onClick={() =>
                downloadCsv([...received].sort((one, other) => one.position - other.position))
              }
              disabled={running || done === 0}
            >
              Download results CSV
            </button>

            <p className="footnote">
              Nothing here is saved anywhere. Close this page and the results are gone, so download
              the CSV if you need them.
            </p>
          </>
        ) : null}

        {/* The same control as the single-label view, for the same reason. */}
        {clearable ? (
          <button className="button button--quiet reset" type="button" onClick={reset}>
            Clear and start another batch
          </button>
        ) : null}

        {!started && !error ? (
          <p className="placeholder">
            Upload the label applications, the label images, or both, then select
            <strong> Check labels</strong>. Results appear here as each label finishes, one row per
            label; select a row to see it field by field.
          </p>
        ) : null}
      </section>
    </div>
  )
}

/** The plain line for an error row, through the same mapping every failure uses. */
function rowMessage(line: BatchLine): string {
  return plainMessage(line.error?.code, line.error?.message)
}

/** Two files are the same file when their name, size and modified time agree. */
function sameFile(one: File, other: File): boolean {
  return (
    one.name === other.name && one.size === other.size && one.lastModified === other.lastModified
  )
}
