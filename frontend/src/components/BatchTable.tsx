/**
 * The batch results table: one row per label, in the order submitted (FR-8,
 * FR-10, NFR-2, NFR-5, ADR 0020).
 *
 * **Submission order, not arrival order.** Rows arrive as the server finishes
 * them (ADR 0006), which is no order an agent chose. The page knows the rows
 * before the batch starts, because it groups the files by the same stem rule
 * the server uses, so every row is on the table from the first line and fills
 * in by position as its line arrives. A row still being read shows as pending
 * rather than as a gap, and a row whose line never arrives shows as not
 * checked rather than vanishing (US-10: nothing is silently dropped).
 *
 * **Selecting a row opens the field-by-field detail**, rendered beside the
 * table by the batch tab in the same component the single-label tab uses. The
 * control is a `<button>` in the row's header cell with `aria-expanded` and
 * `aria-controls` over the detail region, which is the disclosure pattern the
 * typed-fields toggle already uses: reachable by Tab, operable by Enter and
 * Space, and its state change is what a screen reader announces. The open row
 * also carries `aria-current`. Focus never moves; the detail appears under
 * the table and the agent goes to it when they choose.
 *
 * **No sorting, since v1.4.0, and that is a decision.** The v1.3.0 table
 * sorted by label, result and two counts because arrival order was not an
 * order. Submission order is: it is the order the agent's file manager gave,
 * and the rows fill in place, which a sort would fight while the stream is
 * still running. The seven-bucket tally above the table is how an agent finds
 * the rows that need them; a sort is a follow-up if that turns out not to be
 * enough at 300 rows.
 *
 * A real `<table>`, with a caption, column headers and a row header per row,
 * so the relationships are in the markup rather than in the layout (1.3.1).
 */
import { OutcomeBadge } from './OutcomeBadge'
import { Chip } from './Ui'
import { checksPassed, rowOutcome } from '../lib/outcomes'
import type { BatchLine } from '../types'

export interface BatchRow {
  /** 1-based submission order; the key the server's lines fill rows by. */
  position: number
  /** What an agent finds the row by: the label image's name, or the file's. */
  name: string
  /** Every file in the row, in submission order. */
  files: string[]
  /** The server's line for this row, once it has arrived. */
  line: BatchLine | null
}

interface Props {
  rows: BatchRow[]
  /** Whether the stream is still open, which is what makes a missing line "pending". */
  running: boolean
  /** The selected row's position, or null when none is open. */
  selected: number | null
  onSelect: (position: number | null) => void
  /** The id of the detail region the row buttons control. */
  detailId: string
}

/** A value an agent would recognise the label by, from either side of the check. */
function valueOf(line: BatchLine | null, name: string): string {
  const field = line?.result?.fields.find((entry) => entry.name === name)
  if (!field) return ''
  return field.application_value || field.label_value || ''
}

export function BatchTable({ rows, running, selected, onSelect, detailId }: Props) {
  return (
    <div className="table-scroll">
      <table className="results-table batch-table">
        <caption className="visually-hidden">
          Results, one row per label, in the order submitted. Select a label to show its
          field-by-field detail below the table.
        </caption>
        <thead>
          <tr>
            <th scope="col">Label</th>
            <th scope="col">Brand</th>
            <th scope="col">Class or type</th>
            <th scope="col">Outcome</th>
            <th scope="col" className="numeric">
              Checks
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const open = selected === row.position
            const line = row.line
            const outcome = line ? rowOutcome(line) : null
            const outcomes = line?.result?.fields.map((field) => field.outcome) ?? null
            const checks = outcomes ? checksPassed(outcomes) : null
            return (
              <tr
                key={row.position}
                aria-current={open ? 'true' : undefined}
                className={open ? 'batch-table__row--open' : undefined}
              >
                <th scope="row" className="filename">
                  <button
                    type="button"
                    className="row-toggle"
                    aria-expanded={open}
                    aria-controls={detailId}
                    onClick={() => onSelect(open ? null : row.position)}
                  >
                    {row.name}
                  </button>
                </th>
                <td>{valueOf(line, 'brand_name')}</td>
                <td>{valueOf(line, 'class_type')}</td>
                <td>
                  {outcome === null ? (
                    running ? (
                      <Chip dot>Reading...</Chip>
                    ) : (
                      <NotChecked />
                    )
                  ) : outcome === 'error' ? (
                    <NotChecked />
                  ) : (
                    <OutcomeBadge outcome={outcome} />
                  )}
                </td>
                <td className="numeric">{checks ? `${checks.passed} of ${checks.checks}` : ''}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/**
 * The one chip that is not an outcome: the row was not checked at all. Text
 * and a shape of its own, like every outcome chip (NFR-5).
 */
function NotChecked() {
  return (
    <span className="badge badge--mismatch" data-outcome="error">
      <span aria-hidden="true" className="badge__icon badge__icon--text">
        !
      </span>
      <span className="badge__label">Not checked</span>
    </span>
  )
}
