/**
 * The batch tab: one control, rows derived from the files, a table in
 * submission order, and the same detail the single-label tab renders.
 *
 * Requirements: FR-8 (every row identifies its label; one bad file errors that
 * row only), FR-11 (the application side comes from each label's COLA
 * document), FR-12 (one upload, sorted by the tool), FR-10 (a status chip per
 * row, not colour alone), NFR-2 (progress is observable), NFR-5 (the grouping
 * is stated and announced; selection is keyboard operable and its state is
 * announced). Stories: US-9, US-10, US-11, US-23. Decision references: ADR 0020,
 * ADR 0009 for the stem rule it keeps.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BatchTab } from '../components/BatchTab'
import { BatchTable } from '../components/BatchTable'
import type { BatchRow } from '../components/BatchTable'
import { resultsToCsv } from '../lib/csv'
import { rowOutcome } from '../lib/outcomes'
import { describeGroups, groupByStem, groupShape, pairingStem } from '../lib/pairing'
import { plainMessage } from '../lib/plainLanguage'
import { batchLine, classification, fileClassification } from './fixtures'
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

function rowsFrom(lines: (BatchLine | null)[], names?: string[]): BatchRow[] {
  return lines.map((line, at) => ({
    position: at + 1,
    name: line?.filename ?? names?.[at] ?? `file-${at + 1}`,
    files: [line?.filename ?? names?.[at] ?? `file-${at + 1}`],
    line,
  }))
}

describe('the batch results table', () => {
  it('is a real table with a caption, column headers and one row per label', () => {
    render(
      <BatchTable
        rows={rowsFrom(LINES)}
        running={false}
        selected={null}
        onSelect={() => {}}
        detailId="detail"
      />,
    )
    expect(screen.getByRole('table')).toHaveAccessibleName(/one row per label/)
    expect(screen.getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
      'Label',
      'Brand',
      'Class or type',
      'Outcome',
      'Checks',
    ])
    expect(rowNames()).toEqual(['c-clean.png', 'a-broken.png', 'b-review.png'])
    expect(screen.getByText('Not checked')).toBeInTheDocument()
    expect(screen.getByText('Match')).toBeInTheDocument()
    expect(screen.getByText('Does not match')).toBeInTheDocument()
  })

  it('prints the brand, the class or type and the tally the summary line prints', () => {
    render(
      <BatchTable
        rows={rowsFrom(LINES)}
        running={false}
        selected={null}
        onSelect={() => {}}
        detailId="detail"
      />,
    )
    const rows = screen.getAllByRole('row').slice(1)
    // The not-checked chip's aria-hidden glyph is in textContent; the word is
    // what is asserted.
    const cells = (row: HTMLElement) =>
      within(row)
        .getAllByRole('cell')
        .map((cell) => cell.textContent?.replace(/^!/, ''))
    // Brand and class or type come from the application side, which is what
    // the agent is holding; the tally is `checksPassed`, the same count as
    // "5 of 5 checks passed" under a result.
    expect(cells(rows[0])).toEqual(["Stone's Throw", "Stone's Throw", 'Match', '5 of 5'])
    expect(cells(rows[1])).toEqual(['', '', 'Not checked', ''])
    expect(cells(rows[2])).toEqual(["Stone's Throw", "Stone's Throw", 'Does not match', '3 of 5'])
  })

  it('shows a row still being read as pending, and one that never arrived as not checked', () => {
    const { rerender } = render(
      <BatchTable
        rows={rowsFrom([LINES[0], null], ['c-clean.png', 'z-late.png'])}
        running
        selected={null}
        onSelect={() => {}}
        detailId="detail"
      />,
    )
    expect(rowNames()).toEqual(['c-clean.png', 'z-late.png'])
    expect(screen.getByText('Reading...')).toBeInTheDocument()

    rerender(
      <BatchTable
        rows={rowsFrom([LINES[0], null], ['c-clean.png', 'z-late.png'])}
        running={false}
        selected={null}
        onSelect={() => {}}
        detailId="detail"
      />,
    )
    // Nothing is silently dropped (US-10): a gap becomes a visible outcome.
    expect(screen.queryByText('Reading...')).not.toBeInTheDocument()
    expect(screen.getByText('Not checked')).toBeInTheDocument()
  })

  it('reports the worst outcome on a row, so a row is never better than its worst field', () => {
    expect(rowOutcome(LINES[0])).toBe('match')
    expect(rowOutcome(LINES[1])).toBe('error')
    // The row has a needs_review and a mismatch; mismatch wins.
    expect(rowOutcome(LINES[2])).toBe('mismatch')
  })

  it('marks the open row for assistive technology as well as by colour', () => {
    render(
      <BatchTable
        rows={rowsFrom(LINES)}
        running={false}
        selected={2}
        onSelect={() => {}}
        detailId="detail"
      />,
    )
    const rows = screen.getAllByRole('row').slice(1)
    expect(rows[1]).toHaveAttribute('aria-current', 'true')
    expect(rows[0]).not.toHaveAttribute('aria-current')
    const button = within(rows[1]).getByRole('button')
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(button).toHaveAttribute('aria-controls', 'detail')
    expect(within(rows[0]).getByRole('button')).toHaveAttribute('aria-expanded', 'false')
  })
})

describe('how files become labels (ADR 0020)', () => {
  it('groups by stem in order of first appearance, exactly as the server does', () => {
    const groups = groupByStem(['b.pdf', 'a.png', 'B.PNG', 'c.pdf'])
    expect(groups.map((group) => [group.position, group.stem, group.indexes])).toEqual([
      [1, 'b', [0, 2]],
      [2, 'a', [1]],
      [3, 'c', [3]],
    ])
  })

  it('names the shape of a row from what is known of its files', () => {
    expect(groupShape(['application_document', 'label_image'])).toBe('pair')
    expect(groupShape(['application_document'])).toBe('application')
    expect(groupShape(['label_image'])).toBe('image')
    expect(groupShape(['label_image', 'label_image'])).toBe('ambiguous')
    expect(groupShape(['application_document', null])).toBe('reading')
    expect(groupShape(['failed'])).toBe('failed')
  })

  it('describes the rows in one sentence, naming only the shapes present', () => {
    expect(describeGroups([])).toBe('')
    expect(describeGroups(['application'])).toBe('1 label to check, an application on its own.')
    expect(describeGroups(['application', 'application', 'application'])).toBe(
      '3 labels to check, each an application on its own.',
    )
    expect(describeGroups(['pair', 'application', 'image', 'reading'])).toBe(
      '4 labels to check: 1 with an application and an image, 1 application on its own, 1 image on its own, 1 still being read.',
    )
    expect(describeGroups(['ambiguous', 'failed'])).toBe(
      '2 labels to check: 1 with more than one file of the same kind, which cannot be checked, 1 with a file that could not be read.',
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

  it('does not pair a sharp s with a double s, and neither does the server', () => {
    expect(pairingStem('Straße.png')).not.toBe(pairingStem('STRASSE.pdf'))
  })
})

describe('the batch tab', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  /**
   * A fetch that answers both calls the tab makes: `/api/classify` per file,
   * from the file's type, and `/api/verify-batch` from the given lines, one
   * per chunk, with the chunk boundary falling on the record boundary of all
   * but the last, to exercise the buffering in lib/api.ts.
   */
  function api(lines: BatchLine[], sent: FormData[] = []) {
    const encoder = new TextEncoder()
    return vi.fn(async (url: string, init: RequestInit) => {
      const body = init.body as FormData
      if (url === '/api/classify') {
        const file = body.get('files') as File
        const side = file.type === 'application/pdf' ? 'application_document' : 'label_image'
        return {
          ok: true,
          status: 200,
          json: async () =>
            classification({
              files: [fileClassification(file.name, side)],
              application_document: null,
              label_images: side === 'label_image' ? 1 : 0,
            }),
        } as unknown as Response
      }
      sent.push(body)
      let at = 0
      return {
        ok: true,
        status: 200,
        body: {
          getReader() {
            return {
              async read() {
                if (at >= lines.length) return { done: true, value: undefined }
                const text = JSON.stringify(lines[at]) + '\n'
                at += 1
                return { done: false, value: encoder.encode(text) }
              },
            }
          },
        },
      } as unknown as Response
    })
  }

  function png(name: string) {
    return new File([new Uint8Array([1])], name, { type: 'image/png' })
  }

  function pdf(name: string) {
    return new File([new Uint8Array([1])], name, { type: 'application/pdf' })
  }

  const picker = () => screen.getByLabelText('Files for these labels')

  async function chooseFiles(user: ReturnType<typeof userEvent.setup>) {
    await user.upload(picker(), [png('c-clean.png'), png('a-broken.png'), png('b-review.png')])
  }

  async function runBatch(user: ReturnType<typeof userEvent.setup>) {
    await chooseFiles(user)
    await user.click(screen.getByRole('button', { name: /^Check/ }))
  }

  it('takes applications and images through one control and shows what each was taken to be', async () => {
    vi.stubGlobal('fetch', api([]))
    const user = userEvent.setup()
    render(<BatchTab />)
    expect(screen.getAllByLabelText(/Files for/)).toHaveLength(1)
    expect(picker()).toHaveAttribute(
      'accept',
      'application/pdf,image/jpeg,image/png,image/webp,image/tiff',
    )

    await user.upload(picker(), [pdf('0001-stones-throw.pdf'), png('0002-hollow-creek.png')])

    // The same chips the single-label tab puts beside a file (FR-12).
    await waitFor(() => expect(screen.getByText('Label application')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText('Label image')).toBeInTheDocument())
    expect(
      screen.getByText('This is a PDF, so we read it as the label application.'),
    ).toBeInTheDocument()
  })

  it('turns the check on with one file, and says what is missing before that', async () => {
    vi.stubGlobal('fetch', api([]))
    const user = userEvent.setup()
    render(<BatchTab />)
    expect(screen.getByRole('button', { name: /^Check/ })).toBeDisabled()
    expect(screen.getByText('Upload a file to check.')).toBeInTheDocument()

    await user.upload(picker(), pdf('filed.pdf'))

    expect(screen.getByRole('button', { name: 'Check 1 label' })).toBeEnabled()
    expect(screen.queryByText('Upload a file to check.')).not.toBeInTheDocument()
  })

  it('groups files by stem, describes the labels and announces them (NFR-5)', async () => {
    vi.stubGlobal('fetch', api([]))
    const user = userEvent.setup()
    render(<BatchTab />)
    // The region exists, labelled and empty, before anything is chosen (4.1.3).
    expect(screen.getByRole('status', { name: 'Batch pairing' })).toHaveTextContent('')

    await user.upload(picker(), [pdf('a.pdf'), png('A.PNG'), pdf('b.pdf'), png('c.png')])

    await waitFor(() =>
      expect(screen.getByRole('status', { name: 'Batch pairing' })).toHaveTextContent(
        '3 labels to check: 1 with an application and an image, 1 application on its own, 1 image on its own.',
      ),
    )
    expect(screen.getByRole('button', { name: 'Check 3 labels' })).toBeEnabled()
  })

  it('sends everything in one files part, and nothing under the two old names', async () => {
    const sent: FormData[] = []
    vi.stubGlobal('fetch', api([], sent))
    const user = userEvent.setup()
    render(<BatchTab />)
    await user.upload(picker(), [pdf('a.pdf'), png('a.png'), pdf('b.pdf')])
    await user.click(screen.getByRole('button', { name: /^Check/ }))

    await waitFor(() => expect(sent).toHaveLength(1))
    expect(sent[0].getAll('files')).toHaveLength(3)
    expect(sent[0].getAll('images')).toHaveLength(0)
    expect(sent[0].getAll('application_documents')).toHaveLength(0)
  })

  it('renders progress from the stream and then the summary counts', async () => {
    vi.stubGlobal('fetch', api(LINES))
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
    const items = within(screen.getByRole('list', { name: '' })).getAllByRole('listitem')
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

  it('accounts for every row, in a category a reader can name', async () => {
    const rows: BatchLine[] = [
      batchLine('1-match.png', 1, 7, ['match', 'match', 'match', 'match', 'match']),
      batchLine('2-present.png', 2, 7, ['present', 'present', 'present', 'present', 'present']),
      batchLine('3-review.png', 3, 7, ['needs_review', 'match', 'match', 'match', 'match']),
      batchLine('4-mismatch.png', 4, 7, ['mismatch', 'match', 'match', 'match', 'match']),
      batchLine('5-not-compared.png', 5, 7, ['not_compared', 'match', 'match', 'match', 'match']),
      batchLine('6-artwork.png', 6, 7, ['match', 'artwork_derived', 'match', 'match', 'match']),
      batchLine('7-error.png', 7, 7, null),
    ]
    vi.stubGlobal('fetch', api(rows))
    const user = userEvent.setup()
    render(<BatchTab />)
    await user.upload(
      picker(),
      rows.map((row) => png(row.filename!)),
    )
    await user.click(screen.getByRole('button', { name: /^Check/ }))
    await waitFor(() => expect(screen.getByText('7 of 7 labels checked')).toBeInTheDocument())

    const items = within(screen.getByRole('list', { name: '' })).getAllByRole('listitem')
    const counts = items.map((item) => Number(item.textContent?.split(' ')[0]))
    expect(counts).toEqual([1, 1, 1, 1, 1, 1, 1])
    expect(counts.reduce((sum, count) => sum + count, 0)).toBe(rows.length)
    expect(
      within(screen.getByRole('region', { name: 'Results' })).getByRole('status'),
    ).toHaveTextContent(
      'Finished. 7 labels checked: 1 fully matching, 1 passing on what the label carries, with nothing declared, 1 needing review, 1 not matching, 1 with a value not compared, 1 read from the artwork only, 1 could not be checked.',
    )
  })

  it('places every row in submission order, however the lines arrive', async () => {
    // The server finishes rows out of order (ADR 0006); position puts them back.
    const arrival = [LINES[2], LINES[0], LINES[1]].map((line, index) => ({
      ...line,
      index: index + 1,
    }))
    vi.stubGlobal('fetch', api(arrival))
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)

    await waitFor(() => expect(screen.getByText('3 of 3 labels checked')).toBeInTheDocument())
    expect(rowNames()).toEqual(['c-clean.png', 'a-broken.png', 'b-review.png'])
  })

  it('keeps every row that arrived, including the one that failed (US-10)', async () => {
    vi.stubGlobal('fetch', api(LINES))
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)

    await waitFor(() => {
      expect(screen.getAllByRole('row')).toHaveLength(4)
    })
    expect(screen.getByText('Not checked')).toBeInTheDocument()
  })

  it('shows a row whose line never arrived as not checked rather than dropping it', async () => {
    vi.stubGlobal('fetch', api(LINES.slice(0, 2)))
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)

    await waitFor(() => expect(screen.getByText('2 of 3 labels checked')).toBeInTheDocument())
    expect(rowNames()).toEqual(['c-clean.png', 'a-broken.png', 'b-review.png'])
    expect(screen.getAllByText('Not checked')).toHaveLength(2)

    await user.click(screen.getByRole('button', { name: 'b-review.png' }))
    expect(screen.getByText(/No result arrived for this label/)).toBeInTheDocument()
  })

  it('opens the field-by-field detail from the keyboard, in the single-label component', async () => {
    vi.stubGlobal('fetch', api(LINES))
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)
    await waitFor(() => expect(screen.getByText('3 of 3 labels checked')).toBeInTheDocument())

    const toggle = screen.getByRole('button', { name: 'b-review.png' })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    // Nothing is open, so the detail region is out of the tree.
    expect(screen.queryByRole('heading', { name: /^Label 3 of 3/ })).not.toBeInTheDocument()

    toggle.focus()
    await user.keyboard('{Enter}')

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    // Focus stays where it was; the detail appears under the table.
    expect(toggle).toHaveFocus()
    const detail = screen.getByRole('region', { name: 'Label 3 of 3: b-review.png' })
    expect(within(detail).getByText('3 of 5 checks passed')).toBeInTheDocument()
    // The same five cards the single-label tab renders, with the same chips.
    expect(within(detail).getAllByRole('article')).toHaveLength(5)
    expect(within(detail).getByText('Needs review')).toBeInTheDocument()
    expect(within(detail).getByText('Does not match')).toBeInTheDocument()
    expect(within(detail).getByText('This tool recommends. You decide.')).toBeInTheDocument()

    // Space closes it again, because it is a real button.
    await user.keyboard(' ')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('region', { name: /^Label 3 of 3/ })).not.toBeInTheDocument()
  })

  it('shows the plain error for a row that could not be checked, in the detail', async () => {
    vi.stubGlobal('fetch', api(LINES))
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)
    await waitFor(() => expect(screen.getByText('3 of 3 labels checked')).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'a-broken.png' }))
    const detail = screen.getByRole('region', { name: 'Label 2 of 3: a-broken.png' })
    expect(within(detail).getByRole('alert')).toHaveTextContent(plainMessage('unreadable_image'))
    expect(within(detail).getByText('Could not read.')).toBeInTheDocument()
  })

  it('announces progress and then the finished counts (NFR-2, NFR-5)', async () => {
    vi.stubGlobal('fetch', api(LINES))
    const user = userEvent.setup()
    render(<BatchTab />)
    await runBatch(user)

    // Scoped to the results panel: the submission panel has a live region of
    // its own, for the grouping sentence.
    await waitFor(() => {
      expect(
        within(screen.getByRole('region', { name: 'Results' })).getByRole('status'),
      ).toHaveTextContent(/Finished\. 3 labels checked/)
    })
  })

  it('clears the batch and cancels every request still in flight (finding 17)', async () => {
    const signals: AbortSignal[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) => {
        signals.push(init.signal as AbortSignal)
        return new Promise<Response>(() => {}) // never answers
      }),
    )
    const user = userEvent.setup()
    render(<BatchTab />)
    await user.upload(picker(), [pdf('a.pdf'), pdf('b.pdf')])
    await user.click(screen.getByRole('button', { name: /^Check/ }))
    await waitFor(() => expect(signals.length).toBe(3))
    expect(screen.getByText('Checking...')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Clear and start another batch' }))

    expect(signals.every((signal) => signal.aborted)).toBe(true)
    expect(screen.queryByText('a.pdf')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Check/ })).toBeDisabled()
    expect(screen.getByRole('status', { name: 'Batch progress' })).toHaveTextContent(
      'The batch was cleared',
    )
  })

  it('stops a running batch, keeps the rows that arrived, and settles the screen', async () => {
    const signals: AbortSignal[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init: RequestInit) => {
        if (url === '/api/classify') {
          return api([])(url, init)
        }
        // A stream that never ends until the agent stops it.
        return new Promise<Response>((_, reject) => {
          signals.push(init.signal as AbortSignal)
          init.signal?.addEventListener('abort', () =>
            reject(Object.assign(new Error('aborted'), { name: 'AbortError' })),
          )
        })
      }),
    )
    const user = userEvent.setup()
    render(<BatchTab />)
    await user.upload(picker(), [pdf('a.pdf'), pdf('b.pdf')])
    await user.click(screen.getByRole('button', { name: /^Check/ }))
    await waitFor(() => expect(signals).toHaveLength(1))
    expect(screen.getAllByText('Reading...')).toHaveLength(2)

    await user.click(screen.getByRole('button', { name: 'Stop' }))

    expect(signals[0].aborted).toBe(true)
    // The run is over: the check is offered again, the queue is kept, and the
    // rows that never arrived say so rather than staying "Reading...".
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Check 2 labels' })).toBeEnabled(),
    )
    expect(screen.queryByRole('button', { name: 'Stop' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove a.pdf' })).toBeInTheDocument()
    expect(screen.getAllByText('Not checked')).toHaveLength(2)
  })

  it('removes a file from the queue and cancels its classification', async () => {
    const signals: AbortSignal[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn((_url: string, init: RequestInit) => {
        signals.push(init.signal as AbortSignal)
        return new Promise<Response>(() => {})
      }),
    )
    const user = userEvent.setup()
    render(<BatchTab />)
    await user.upload(picker(), [pdf('a.pdf')])
    await waitFor(() => expect(signals.length).toBe(1))

    await user.click(screen.getByRole('button', { name: 'Remove a.pdf' }))

    expect(signals[0].aborted).toBe(true)
    expect(screen.queryByText('a.pdf')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Check/ })).toBeDisabled()
  })

  it('keeps the naming convention off the check screen (it is on Help)', () => {
    vi.stubGlobal('fetch', api([]))
    render(<BatchTab />)
    expect(screen.queryByText(/matched by name/)).not.toBeInTheDocument()
    expect(screen.queryByText('0001-stones-throw.pdf')).not.toBeInTheDocument()
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
 * The two batch rows that cannot be checked, and the one batch-level refusal
 * (ADR 0020). `uploadList.test.tsx` reads every code off the backend source,
 * so this only asserts that the batch lines say the thing an agent has to act
 * on. The ADR 0009 codes for an unmatched or missing partner are gone, because
 * a file on its own is a valid row now.
 */
describe('the batch error lines say what to do', () => {
  it('sends a label with several photographs to the single-label tab', () => {
    expect(plainMessage('duplicate_label_stem')).toContain('Check one label')
  })

  it('names the ambiguity for two applications under one name', () => {
    expect(plainMessage('duplicate_application_document')).toContain('application')
  })

  it('no longer tells an agent to attach a document for every image', () => {
    expect(plainMessage('empty_batch')).not.toContain('COLA document for each')
    expect(plainMessage('empty_batch')).toContain('or both')
  })
})
