/**
 * The batch results as a CSV, built in the browser.
 *
 * Built client-side because of D-9: nothing is persisted server-side, so there
 * is no results resource to download. The rows the agent is looking at are the
 * only copy, and this turns that copy into a file without a round trip.
 *
 * One row per label per field, rather than one row per label with five columns.
 * A long shape survives a filter and a pivot in a spreadsheet, which is what an
 * agent handling a 300-label drop will actually do with it.
 */
import type { BatchLine } from '../types'

const HEADER = [
  'filename',
  'status',
  'field',
  'label_value',
  'application_value',
  'outcome',
  'score',
  'reason',
]

/** RFC 4180 quoting: double the quotes, wrap anything that could break a cell. */
function cell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return ''
  const text = String(value)
  // A leading =, +, - or @ is treated as a formula by Excel and Sheets. Prefix
  // with an apostrophe so a reason string starting with one is read as text.
  const guarded = /^[=+\-@]/.test(text) ? `'${text}` : text
  return /["\n\r,]/.test(guarded) ? `"${guarded.replace(/"/g, '""')}"` : guarded
}

export function resultsToCsv(lines: BatchLine[]): string {
  const rows = [HEADER.join(',')]
  for (const line of lines) {
    if (line.status === 'error' || !line.result) {
      rows.push(
        [
          cell(line.filename),
          'error',
          '',
          '',
          '',
          '',
          '',
          cell(line.error?.message ?? 'Not checked.'),
        ].join(','),
      )
      continue
    }
    for (const field of line.result.fields) {
      rows.push(
        [
          cell(line.filename),
          'checked',
          cell(field.display_name),
          cell(field.label_value),
          cell(field.application_value),
          cell(field.outcome),
          cell(field.score === null ? '' : field.score.toFixed(1)),
          cell(field.reason),
        ].join(','),
      )
    }
  }
  return rows.join('\r\n')
}

/** Hand the CSV to the browser as a download. Nothing leaves the machine. */
export function downloadCsv(lines: BatchLine[], filename = 'label-check-results.csv'): void {
  const blob = new Blob([resultsToCsv(lines)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
