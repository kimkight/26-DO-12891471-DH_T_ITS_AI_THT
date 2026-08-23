/**
 * The batch results table, sortable, with a status chip per row (FR-8, FR-10).
 *
 * Sorting is client-side over rows already received, and it is stable, so a
 * sort applied while the stream is still running does not reorder what is
 * already on screen out from under the agent's eye. Rows arrive in completion
 * order rather than submission order (ADR 0006), so an unsorted table is not
 * in any order an agent chose; "Label" ascending is therefore the default.
 *
 * Sorting is driven by a `<button>` inside each `<th>` with `aria-sort` on the
 * header, rather than a click handler on the cell. A div with an onClick is not
 * reachable by keyboard and announces nothing (NFR-5).
 */
import { useMemo, useState } from 'react'
import { OutcomeBadge } from './OutcomeBadge'
import { countOf, presentation, rowOutcome } from '../lib/outcomes'
import type { BatchLine } from '../types'

type Column = 'filename' | 'status' | 'needs_review' | 'mismatch'
type Direction = 'ascending' | 'descending'

const COLUMNS: { key: Column; label: string; numeric?: boolean }[] = [
  { key: 'filename', label: 'Label' },
  { key: 'status', label: 'Result' },
  // Named as counts, not as outcomes. "Does not match" here would repeat the
  // wording of the chip in the Result column and make "the mismatch column"
  // and "a mismatch chip" the same phrase for two different things.
  { key: 'needs_review', label: 'Fields to review', numeric: true },
  { key: 'mismatch', label: 'Fields not matching', numeric: true },
]

// Sort order for the status column: the rows an agent has to act on first.
const SEVERITY: Record<string, number> = {
  error: 0,
  mismatch: 1,
  needs_review: 2,
  not_compared: 3,
  match: 4,
}

export function BatchTable({ lines }: { lines: BatchLine[] }) {
  const [column, setColumn] = useState<Column>('filename')
  const [direction, setDirection] = useState<Direction>('ascending')

  const sorted = useMemo(() => {
    const sign = direction === 'ascending' ? 1 : -1
    const key = (line: BatchLine): number | string => {
      switch (column) {
        case 'filename':
          return line.filename ?? ''
        case 'status':
          return SEVERITY[rowOutcome(line)] ?? 99
        case 'needs_review':
          return countOf(line, 'needs_review')
        case 'mismatch':
          return countOf(line, 'mismatch')
      }
    }
    // Array.prototype.sort is stable in every engine this targets, so equal
    // keys keep the order the rows arrived in.
    return [...lines].sort((a, b) => {
      const left = key(a)
      const right = key(b)
      if (typeof left === 'string' && typeof right === 'string') {
        return sign * left.localeCompare(right)
      }
      return sign * (Number(left) - Number(right))
    })
  }, [lines, column, direction])

  function sortBy(next: Column) {
    if (next === column) {
      setDirection(direction === 'ascending' ? 'descending' : 'ascending')
      return
    }
    setColumn(next)
    setDirection('ascending')
  }

  return (
    <div className="table-scroll">
      <table className="results-table">
        <caption className="visually-hidden">
          Batch results, one row per label. Select a column heading to sort.
        </caption>
        <thead>
          <tr>
            {COLUMNS.map(({ key, label, numeric }) => (
              <th
                key={key}
                scope="col"
                className={numeric ? 'numeric' : undefined}
                aria-sort={column === key ? direction : 'none'}
              >
                <button type="button" className="sort" onClick={() => sortBy(key)}>
                  {label}
                  <span className="sort__arrow" aria-hidden="true">
                    {column === key ? (direction === 'ascending' ? '↑' : '↓') : '↕'}
                  </span>
                </button>
              </th>
            ))}
            <th scope="col">Detail</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((line) => {
            const outcome = rowOutcome(line)
            return (
              <tr key={`${line.filename}-${line.index}`}>
                <th scope="row" className="filename">
                  {line.filename}
                </th>
                <td>
                  {outcome === 'error' ? (
                    <span className="badge badge--mismatch" data-outcome="error">
                      <span aria-hidden="true" className="badge__icon badge__icon--text">
                        !
                      </span>
                      <span className="badge__label">Not checked</span>
                    </span>
                  ) : (
                    <OutcomeBadge outcome={outcome} />
                  )}
                </td>
                <td className="numeric">{line.result ? countOf(line, 'needs_review') : ''}</td>
                <td className="numeric">{line.result ? countOf(line, 'mismatch') : ''}</td>
                <td className="detail">{line.error ? line.error.message : summarize(line)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/** The row's own one-line summary, so the table says something without expanding. */
function summarize(line: BatchLine): string {
  if (!line.result) return ''
  const attention = line.result.fields.filter(
    (field) => field.outcome === 'needs_review' || field.outcome === 'mismatch',
  )
  if (!attention.length) return 'All five fields match.'
  return attention
    .map((field) => `${field.display_name} ${presentation(field.outcome).spoken}`)
    .join('. ')
}
