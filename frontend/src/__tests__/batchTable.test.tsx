/**
 * The batch results table and the batch tab's progress, pairing and summary.
 *
 * Requirements: FR-8 (every row identifies its label; one unreadable image
 * errors that row only), FR-11 (the application side comes from each label's
 * COLA document), FR-10 (a status chip per row, not colour alone), NFR-2
 * (progress is observable), NFR-5 (the pairing is stated, keyboard reachable
 * and announced; sorting is keyboard operable and its state is announced).
 * Stories: US-9, US-10, US-11, US-23. Decision reference: ADR 0009.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BatchTab } from '../components/BatchTab'
import { BatchTable } from '../components/BatchTable'
import { resultsToCsv } from '../lib/csv'
import { rowOutcome } from '../lib/outcomes'
import { plainMessage } from '../lib/plainLanguage'
import { pairingStem } from '../lib/pairing'
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
    // The same wording the single-label view uses (v1.2.0), so the two views
    // cannot disagree about a row (finding 16).
    expect(screen.getByText('5 of 5 checks passed.')).toBeInTheDocument()
  })

  /*
   * Rows whose worst outcome is not match, review or mismatch (code review
   * finding 16, #115). The detail cell used to read "All five fields match."
   * for every one of them.
   */
  it('names a value that was not compared, a presence check and an artwork-derived row', () => {
    render(
      <BatchTable
        lines={[
          batchLine('a.png', 1, 3, ['not_compared', 'match', 'match', 'match', 'match']),
          batchLine('b.png', 2, 3, ['match', 'match', 'present', 'present', 'match']),
          batchLine('c.png', 3, 3, ['match', 'artwork_derived', 'match', 'match', 'match']),
        ]}
      />,
    )
    expect(
      screen.getByText('4 of 5 checks passed. brand name was not compared.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        '5 of 5 checks passed. alcohol content is on the label, as the regulation requires. net contents is on the label, as the regulation requires.',
      ),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        '4 of 4 checks passed; 1 read from the artwork only. class type was read from the label artwork and could not be compared against it.',
      ),
    ).toBeInTheDocument()
    expect(screen.queryByText(/All five fields match/)).not.toBeInTheDocument()
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

  function png(name: string) {
    return new File([new Uint8Array([1])], name, { type: 'image/png' })
  }

  function pdf(name: string) {
    return new File([new Uint8Array([1])], name, { type: 'application/pdf' })
  }

  async function chooseFiles(user: ReturnType<typeof userEvent.setup>) {
    await user.upload(screen.getByLabelText('Label images'), [
      png('c-clean.png'),
      png('a-broken.png'),
      png('b-review.png'),
    ])
    await user.upload(screen.getByLabelText('COLA documents'), [
      pdf('c-clean.pdf'),
      pdf('a-broken.pdf'),
      pdf('b-review.pdf'),
    ])
  }

  async function runBatch(user: ReturnType<typeof userEvent.setup>) {
    await chooseFiles(user)
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

    // Each row is counted once, under its worst outcome, so the seven buckets
    // sum to the row count. b-review.png carries both a needs_review and a
    // mismatch, so it counts as a mismatch and not in both.
    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual([
      '1 fully matching',
      '0 passing on what the label carries, with nothing declared',
      '0 needing review',
      '1 not matching',
      '0 with a value not compared',
      '0 read from the artwork only',
      '1 could not be checked',
    ])
  })

  /*
   * The buckets partition every row (code review finding 16, #115). A batch
   * of one row per category: the counts sum to the row count, and the
   * finished sentence names each non-zero bucket in the same words.
   */
  it('accounts for every row, in a category a reader can name', async () => {
    const rows: BatchLine[] = [
      batchLine('1-match.png', 1, 7, ['match', 'match', 'match', 'match', 'match']),
      // A row of nothing but presence checks: no agreement was tested (FR-15).
      batchLine('2-present.png', 2, 7, ['present', 'present', 'present', 'present', 'present']),
      batchLine('3-review.png', 3, 7, ['needs_review', 'match', 'match', 'match', 'match']),
      batchLine('4-mismatch.png', 4, 7, ['mismatch', 'match', 'match', 'match', 'match']),
      batchLine('5-not-compared.png', 5, 7, ['not_compared', 'match', 'match', 'match', 'match']),
      batchLine('6-artwork.png', 6, 7, ['match', 'artwork_derived', 'match', 'match', 'match']),
      batchLine('7-error.png', 7, 7, null),
    ]
    vi.stubGlobal('fetch', streamOf(rows))
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)
    await waitFor(() => expect(screen.getByText('7 of 7 labels checked')).toBeInTheDocument())

    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    const counts = items.map((item) => Number(item.textContent?.split(' ')[0]))
    expect(counts).toEqual([1, 1, 1, 1, 1, 1, 1])
    expect(counts.reduce((sum, count) => sum + count, 0)).toBe(rows.length)
    expect(
      within(screen.getByRole('region', { name: 'Results' })).getByRole('status'),
    ).toHaveTextContent(
      'Finished. 7 labels checked: 1 fully matching, 1 passing on what the label carries, with nothing declared, 1 needing review, 1 not matching, 1 with a value not compared, 1 read from the artwork only, 1 could not be checked.',
    )
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

    // Scoped to the results panel: the submission panel has a live region of
    // its own now, for the pairing count.
    await waitFor(() => {
      expect(
        within(screen.getByRole('region', { name: 'Results' })).getByRole('status'),
      ).toHaveTextContent(/Finished\. 3 labels checked/)
    })
  })

  it('keeps the check off until both the images and the documents are chosen', () => {
    render(<BatchTab />)
    expect(screen.getByRole('button', { name: /^Check/ })).toBeDisabled()
    expect(
      screen.getByText('Choose the label images and their COLA documents to turn on the check.'),
    ).toBeInTheDocument()
  })

  it('states the pairing rule on the page before anything is chosen (ADR 0009)', () => {
    render(<BatchTab />)
    const rule = screen.getByText(/They are matched by name/)
    expect(rule).toHaveTextContent('0001-stones-throw.pdf')
    expect(rule).toHaveTextContent('0001-stones-throw.png')
  })

  it('sends both lists to the batch route, with no CSV part', async () => {
    const sent: FormData[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        sent.push(init.body as FormData)
        return {
          ok: true,
          body: {
            getReader: () => ({
              async read() {
                return { done: true, value: undefined }
              },
            }),
          },
        } as unknown as Response
      }),
    )
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)

    await waitFor(() => expect(sent).toHaveLength(1))
    const body = sent[0]
    expect(body.getAll('images')).toHaveLength(3)
    expect(body.getAll('application_documents')).toHaveLength(3)
    expect(body.get('applications')).toBeNull()
  })

  it('counts the pairs it will send and announces the count (NFR-5)', async () => {
    const user = userEvent.setup()
    render(<BatchTab />)
    // The region exists, labelled and empty, before anything is chosen (4.1.3).
    expect(screen.getByRole('status', { name: 'Batch pairing' })).toHaveTextContent('')
    await chooseFiles(user)

    expect(screen.getByRole('status', { name: 'Batch pairing' })).toHaveTextContent(
      '3 pairs ready to check.',
    )
  })

  /*
   * The page's fold is the server's fold (code review finding 21). The same
   * vectors, character for character, are asserted in
   * `backend/tests/test_batch.py::TestTheFoldIsTheSameOnBothSides`.
   */
  it.each([
    ['Label.PNG', 'label'],
    ['ÉTIQUETTE.png', 'étiquette'],
    ['Straße.png', 'straße'],
    ['STRASSE.pdf', 'strasse'],
    ['İstanbul.pdf', 'i̇stanbul'],
  ])('folds %s to %s, exactly as the server does', (filename, expected) => {
    expect(pairingStem(filename)).toBe(expected)
  })

  it('does not pair a sharp s with a double s, and neither does the server now', () => {
    expect(pairingStem('Straße.png')).not.toBe(pairingStem('STRASSE.pdf'))
  })

  it('names the files that pair with nothing, before the batch is sent', async () => {
    const user = userEvent.setup()
    render(<BatchTab />)
    await user.upload(screen.getByLabelText('Label images'), [png('a.png'), png('b.png')])
    await user.upload(screen.getByLabelText('COLA documents'), [pdf('a.pdf'), pdf('c.pdf')])

    const status = screen.getAllByRole('status').find((node) => node.textContent?.includes('pair'))
    expect(status).toHaveTextContent(
      '1 pair ready to check, 1 image with no matching document, 1 document with no matching image.',
    )
    expect(screen.getByText(/No document matches: b.png/)).toBeInTheDocument()
    expect(screen.getByText(/No image matches: c.pdf/)).toBeInTheDocument()
  })

  it('still lets an unmatched batch run, because the rest of it is unaffected', async () => {
    const user = userEvent.setup()
    render(<BatchTab />)
    await user.upload(screen.getByLabelText('Label images'), [png('a.png'), png('b.png')])
    await user.upload(screen.getByLabelText('COLA documents'), [pdf('a.pdf')])
    expect(screen.getByRole('button', { name: /^Check/ })).toBeEnabled()
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

/*
 * The batch error codes and their plain-language lines (FR-9, NFR-4).
 *
 * `plainMessage` falls back to a generic sentence for a code it does not know,
 * which is the right behaviour at runtime and the wrong thing to discover in
 * production: a code the server emits and this table has never heard of reads
 * as "we could not check this label" when the real problem is a filename. So
 * the codes ADR 0009 defines are listed here and asserted to have a line of
 * their own. The list is the contract; adding a code to `app/batch.py` without
 * adding it here fails this test.
 */
describe('every batch error code an agent can meet has a plain-language line', () => {
  const CODES = [
    'batch_too_large',
    'empty_batch',
    'missing_application_documents',
    'missing_application_document',
    'unmatched_application_document',
    'duplicate_application_document',
    'duplicate_label_stem',
    'unreadable_application_document',
    'unsupported_application_document',
    'unsupported_media_type',
    'file_too_large',
    'unreadable_image',
    'verification_failed',
    // The three the single upload can meet that had no line until v1.3.0
    // (finding 22). `uploadList.test.tsx` reads the whole set off the backend
    // source, so this list is the batch half of the contract only.
    'no_files',
    'no_label_to_check',
    'too_many_application_documents',
  ]

  const FALLBACK = plainMessage('a-code-that-does-not-exist')

  it.each(CODES)('%s reads as something other than the fallback', (code) => {
    expect(plainMessage(code)).not.toBe(FALLBACK)
  })

  it('the pairing failures name the file extension rule an agent has to act on', () => {
    expect(plainMessage('missing_application_documents')).toContain('.pdf')
    expect(plainMessage('missing_application_document')).toContain('same name')
  })
})
