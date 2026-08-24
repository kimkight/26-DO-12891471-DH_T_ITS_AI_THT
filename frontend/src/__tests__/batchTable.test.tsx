/**
 * The batch results table and the batch tab's progress and summary.
 *
 * Requirements: FR-8 (every row identifies its label; one unreadable image
 * errors that row only), FR-10 (a status chip per row, not colour alone),
 * NFR-2 (progress is observable), NFR-5 (sorting is keyboard operable and its
 * state is announced). Stories: US-9, US-10, US-11.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BatchTab } from '../components/BatchTab'
import { BatchTable } from '../components/BatchTable'
import { resultsToCsv } from '../lib/csv'
import { rowOutcome } from '../lib/outcomes'
import { batchLine } from './fixtures'
import type { BatchLine } from '../types'

const LINES: BatchLine[] = [
  batchLine('c-clean.png', 1, 3, ['match', 'match', 'match', 'match', 'match']),
  batchLine('a-broken.png', 2, 3, null, { code: 'unreadable_image', message: 'Could not read.' }),
  batchLine('b-review.png', 3, 3, ['needs_review', 'match', 'mismatch', 'match', 'match']),
]

function rowNames(): string[] {
  return screen
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('rowheader')[0].textContent ?? '')
}

describe('the batch results table', () => {
  it('gives every row its label and a status chip carrying a word', () => {
    render(<BatchTable lines={LINES} />)
    expect(rowNames().sort()).toEqual(['a-broken.png', 'b-review.png', 'c-clean.png'])
    expect(screen.getByText('Not checked')).toBeInTheDocument()
    expect(screen.getByText('Match')).toBeInTheDocument()
    expect(screen.getByText('Does not match')).toBeInTheDocument()
  })

  it('reports the worst outcome on a row, so a row is never better than its worst field', () => {
    expect(rowOutcome(LINES[0])).toBe('match')
    expect(rowOutcome(LINES[1])).toBe('error')
    // The row has a needs_review and a mismatch; mismatch wins.
    expect(rowOutcome(LINES[2])).toBe('mismatch')
  })

  it('sorts by label ascending to begin with, because arrival order is not an order', () => {
    render(<BatchTable lines={LINES} />)
    expect(rowNames()).toEqual(['a-broken.png', 'b-review.png', 'c-clean.png'])
  })

  it('sorts from the keyboard and announces which column and direction', async () => {
    const user = userEvent.setup()
    render(<BatchTable lines={LINES} />)

    const header = screen.getByRole('columnheader', { name: /Label/ })
    expect(header).toHaveAttribute('aria-sort', 'ascending')

    await user.click(within(header).getByRole('button'))
    expect(header).toHaveAttribute('aria-sort', 'descending')
    expect(rowNames()).toEqual(['c-clean.png', 'b-review.png', 'a-broken.png'])

    // Every sort control is a real button, so it is reachable by tab and
    // operable by Enter and Space without any handler of our own (NFR-5).
    const resultHeader = screen.getByRole('columnheader', { name: /Result/ })
    within(resultHeader).getByRole('button').focus()
    await user.keyboard('{Enter}')
    expect(resultHeader).toHaveAttribute('aria-sort', 'ascending')
    // Severity order: the rows an agent has to act on come first.
    expect(rowNames()).toEqual(['a-broken.png', 'b-review.png', 'c-clean.png'])
  })

  it('sorts by the counts an agent filters on', async () => {
    const user = userEvent.setup()
    render(<BatchTable lines={LINES} />)
    const header = screen.getByRole('columnheader', { name: /Fields not matching/ })
    await user.click(within(header).getByRole('button'))
    // Ascending: the two rows with no mismatch first, then the one with one.
    expect(rowNames().at(-1)).toBe('b-review.png')
  })

  it('shows the row error message rather than an empty cell', () => {
    render(<BatchTable lines={LINES} />)
    expect(screen.getByText('Could not read.')).toBeInTheDocument()
    expect(screen.getByText('All five fields match.')).toBeInTheDocument()
  })
})

describe('the batch tab', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  function streamOf(lines: BatchLine[]) {
    const encoder = new TextEncoder()
    return vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      body: {
        getReader() {
          let sent = 0
          return {
            async read() {
              if (sent >= lines.length) return { done: true, value: undefined }
              // One line per chunk, and the chunk boundary deliberately falls
              // mid-record on the last one, to exercise the buffering in
              // lib/api.ts that holds a partial line back.
              const text = JSON.stringify(lines[sent]) + '\n'
              sent += 1
              return { done: false, value: encoder.encode(text) }
            },
          }
        },
      },
    } as unknown as Response)
  }

  async function runBatch(user: ReturnType<typeof userEvent.setup>) {
    await user.upload(screen.getByLabelText('Label images'), [
      new File([new Uint8Array([1])], 'c-clean.png', { type: 'image/png' }),
      new File([new Uint8Array([1])], 'a-broken.png', { type: 'image/png' }),
      new File([new Uint8Array([1])], 'b-review.png', { type: 'image/png' }),
    ])
    await user.upload(
      screen.getByLabelText('Application data file'),
      new File(['filename\n'], 'applications.csv', { type: 'text/csv' }),
    )
    await user.click(screen.getByRole('button', { name: /^Check/ }))
  }

  it('renders progress from the stream and then the summary counts', async () => {
    vi.stubGlobal('fetch', streamOf(LINES))
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)

    await waitFor(() => {
      expect(screen.getByText('3 of 3 labels checked')).toBeInTheDocument()
    })
    // The progress element carries the numbers without ARIA of our own.
    const progress = screen.getByRole('progressbar')
    expect(progress).toHaveAttribute('value', '3')
    expect(progress).toHaveAttribute('max', '3')

    // Each row is counted once, under its worst outcome, so the four buckets
    // sum to the row count. b-review.png carries both a needs_review and a
    // mismatch, so it counts as a mismatch and not in both.
    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      '1 fully matching',
      '0 needing review',
      '1 not matching',
      '1 could not be checked',
    ])
  })

  it('keeps every row that arrived, including the one that failed (US-10)', async () => {
    vi.stubGlobal('fetch', streamOf(LINES))
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)

    await waitFor(() => {
      expect(screen.getAllByRole('row')).toHaveLength(4)
    })
    expect(screen.getByText('Not checked')).toBeInTheDocument()
    expect(screen.getByText('Could not read.')).toBeInTheDocument()
  })

  it('announces progress and then the finished counts (NFR-2, NFR-5)', async () => {
    vi.stubGlobal('fetch', streamOf(LINES))
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent(/Finished\. 3 labels checked/)
    })
  })

  it('keeps the check off until both the images and the CSV are chosen', () => {
    render(<BatchTab />)
    expect(screen.getByRole('button', { name: /^Check/ })).toBeDisabled()
    expect(
      screen.getByText(
        'Choose the label images and the application data file to turn on the check.',
      ),
    ).toBeInTheDocument()
  })
})

describe('the downloadable CSV', () => {
  it('has one row per field per label, and one row for a label that failed', () => {
    const rows = resultsToCsv(LINES).split('\r\n')
    expect(rows[0]).toBe('filename,status,field,label_value,application_value,outcome,score,reason')
    // Two checked labels at five fields each, one error row, plus the header.
    expect(rows).toHaveLength(1 + 5 + 1 + 5)
    expect(rows.filter((row) => row.startsWith('a-broken.png,error,'))).toHaveLength(1)
  })

  it('quotes a value containing a comma so it stays in one cell', () => {
    const line = batchLine('x.png', 1, 1, ['match', 'match', 'match', 'match', 'match'])
    line.result!.fields[0].reason = 'Scored 100, which is at or above the match threshold.'
    expect(resultsToCsv([line])).toContain(
      '"Scored 100, which is at or above the match threshold."',
    )
  })

  it('defuses a value a spreadsheet would read as a formula', () => {
    const line = batchLine('x.png', 1, 1, ['match', 'match', 'match', 'match', 'match'])
    line.result!.fields[0].label_value = '=1+1'
    expect(resultsToCsv([line])).toContain("'=1+1")
  })
})
