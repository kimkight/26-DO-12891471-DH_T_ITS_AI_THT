/**
 * The result panel has a word budget, and it is asserted rather than intended.
 *
 * The author, on the released build: "I don't need the time listed on the screen
 * think about what a regular application looks like do not put all these extra
 * words on the screen that should not be there."
 *
 * She is right, and the wordiness accumulated one honest sentence at a time.
 * Every paragraph that was added over the last four sessions was true and was
 * added for a reason; the sum of them is a panel that spends a hundred and fifty
 * words explaining a single row, which is not what Sarah Chen's "clean, obvious,
 * no hunting for buttons" looks like and not what "something my mother could
 * figure out" reads like.
 *
 * **A budget is the only thing that holds.** A rule saying "keep it short" is
 * obeyed by whoever reads it and by nobody who does not, and the next honest
 * sentence goes in the same way the last twelve did. A number in a test is a
 * thing a pull request has to argue with.
 *
 * The budgets below are set above what the panel actually renders, with room for
 * one more row and a little wording drift, and well under what it rendered
 * before. They are ceilings, not targets: a panel that comes in far under is not
 * failing anything.
 *
 * Requirements: NFR-4 (simplicity of the interface), NFR-5 (shorter copy must
 * not become vaguer copy for a screen reader; `liveRegion.test.tsx` and
 * `outcomes.test.tsx` hold that end), FR-10 (the row still shows both values and
 * the evidence).
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SingleLabelTab } from '../components/SingleLabelTab'
import {
  classification,
  field,
  fileClassification,
  phaseTimings,
  photo,
  verification,
  warningDetail,
} from './fixtures'
import type { VerificationResult } from '../types'

/**
 * A clean single-label result: five rows, everything matching, one photograph.
 *
 * The best case on purpose. It is the panel an agent sees most often, it is the
 * one the author was looking at, and it is the one where every extra word is
 * least earned: nothing on it needs acting on.
 */
function cleanResult(): VerificationResult {
  const base = verification()
  return {
    ...base,
    fields: [
      field('brand_name', 'match', {
        display_name: 'Brand name',
        label_value: "STONE'S THROW",
        application_value: "Stone's Throw",
        label_region: { column: 0, block: 1 },
        reason:
          `'Stone's Throw' was found on the label, in column 0, block 1, printed as ` +
          `'STONE'S THROW'.`,
      }),
      field('class_type', 'match', {
        display_name: 'Class or type designation',
        label_value: 'Kentucky Straight Bourbon Whiskey',
        application_value: 'Kentucky Straight Bourbon Whiskey',
        reason: 'Found on the label, in column 0, block 2.',
      }),
      field('alcohol_content', 'match', {
        display_name: 'Alcohol content',
        label_value: '45% Alc./Vol. (90 Proof)',
        application_value: '45',
        reason: 'Label 45 percent and application 45 percent are numerically equal.',
      }),
      field('net_contents', 'match', {
        display_name: 'Net contents',
        label_value: '750 mL',
        application_value: '750 mL',
        reason: '750 mL on both sides. Standards of fill are not validated (A-13).',
      }),
      field('government_warning', 'match', {
        display_name: 'Government warning statement',
        reason: 'The statement matches 27 CFR 16.21 word for word.',
      }),
    ],
    warning_detail: warningDetail(),
    photos: [photo()],
    timings: phaseTimings(),
  }
}

const CLASSIFIED = classification({
  files: [fileClassification('label.png')],
  application_document: null,
  label_images: 1,
})

function stub(result: VerificationResult) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url === '/api/classify') {
        return { ok: true, status: 200, json: async () => CLASSIFIED } as Response
      }
      return { ok: true, status: 200, json: async () => result } as Response
    }),
  )
}

async function renderResult(result: VerificationResult = cleanResult()) {
  const user = userEvent.setup()
  stub(result)
  render(<SingleLabelTab />)
  await user.upload(
    screen.getByLabelText('Files for this label'),
    new File([new Uint8Array([137, 80])], 'label.png', { type: 'image/png' }),
  )
  await user.click(screen.getByRole('button', { name: 'Check this label' }))
  await waitFor(() => expect(document.querySelector('.summary-line')).not.toBeNull())
}

/**
 * The words a sighted agent actually reads in the results panel.
 *
 * Visually hidden text is excluded, because it is not on the screen: the live
 * region says the same thing again for a screen reader by design, and counting
 * it would penalise the accessibility work rather than the copy.
 */
function panelWords(): number {
  const panel = document.querySelector('[aria-labelledby="results-heading"]')
  if (!panel) throw new Error('the results panel is not on the page')
  const clone = panel.cloneNode(true) as HTMLElement
  clone.querySelectorAll('.visually-hidden').forEach((node) => node.remove())
  return (clone.textContent ?? '').trim().split(/\s+/).filter(Boolean).length
}

function rowWords(name: string): number {
  const card = document.querySelector(`article[aria-labelledby="card-${name}"]`)
  if (!card) throw new Error(`no card for ${name}`)
  const clone = card.cloneNode(true) as HTMLElement
  clone.querySelectorAll('.visually-hidden').forEach((node) => node.remove())
  return (clone.textContent ?? '').trim().split(/\s+/).filter(Boolean).length
}

afterEach(() => vi.unstubAllGlobals())

/**
 * The author's own submission: the COLA document uploaded alone, so the artwork
 * inside it is standing in as the label side (ADR 0010, ADR 0013).
 *
 * This is the wordy case and the one she was looking at. Two of the rows carry
 * the fifth outcome, and each of those used to print two long paragraphs saying
 * the same thing twice; the self-consistency explanation was on the panel and on
 * every affected row.
 */
function artworkDerivedResult(): VerificationResult {
  const base = cleanResult()
  return {
    ...base,
    fields: base.fields.map((row) =>
      row.name === 'alcohol_content' || row.name === 'net_contents'
        ? {
            ...row,
            outcome: 'artwork_derived' as const,
            score: null,
            application_value_source: 'parsed_from_artwork' as const,
            // The API's own reason for this row, verbatim, so the count is of
            // what an agent reads rather than of a placeholder.
            reason:
              `${row.display_name} was read from the artwork that is also the ` +
              'label side here, so this shows the artwork carries the value and ' +
              'nothing about what the applicant declared.',
          }
        : row,
    ),
    photos: [photo(1, { origin: 'application_artwork' })],
    label_source: 'application_artwork' as const,
    self_consistency_note: 'Some of this was read from the label artwork inside the application.',
  }
}

/*
 * Measured on this branch's merge base and on its head, same fixtures, same
 * counting. The budgets below sit above the right-hand column with room for one
 * more row and some wording drift, and well under the left one.
 *
 * =========================================  ======  =====
 * measurement                                before  after
 * =========================================  ======  =====
 * clean five-row panel                          246    157
 * one row that matched                           26     26
 * the author's own submission, whole panel      584    253
 * one artwork-derived row on it                 159     51
 * =========================================  ======  =====
 *
 * 159 words on one row is the "about 150 words explaining a single row" the
 * author was looking at.
 */
describe('the result panel fits on a screen', () => {
  it('spends fewer than 200 words on a clean five-row result', async () => {
    await renderResult()
    expect(panelWords()).toBeLessThan(200)
  })

  it('spends fewer than 40 words on a row that matched', async () => {
    await renderResult()
    expect(rowWords('brand_name')).toBeLessThan(40)
  })

  it('stays inside its budget on the wordiest submission there is', async () => {
    await renderResult(artworkDerivedResult())
    expect(panelWords()).toBeLessThan(300)
  })

  it('spends fewer than 70 words on an artwork-derived row', async () => {
    await renderResult(artworkDerivedResult())
    expect(rowWords('alcohol_content')).toBeLessThan(70)
  })
})

describe('what came off the screen', () => {
  it('shows no elapsed time and no phase disclosure', async () => {
    await renderResult()
    expect(screen.queryByText(/Checked in/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Where the time went/)).not.toBeInTheDocument()
  })

  it('says the artwork limitation once, not on every row that carries it', async () => {
    await renderResult(artworkDerivedResult())
    expect(screen.getAllByText(/not a photo of a bottle/i)).toHaveLength(1)
  })

  it('keeps the sentence that says who decides', async () => {
    /*
     * Cutting words is not licence to drop a claim. This one is the whole of
     * the tool's posture, it is three words long, and it stays.
     */
    await renderResult()
    expect(screen.getByText(/This tool recommends\. You decide\./)).toBeInTheDocument()
  })
})
