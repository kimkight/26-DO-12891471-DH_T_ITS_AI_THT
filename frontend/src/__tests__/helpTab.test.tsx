/**
 * The check screen gets quiet, and the words go to Help (US-28, NFR-4).
 *
 * The author, on the released build: "this has way too many words on the screen.
 * create a help me tab and put all of the text you are removing plus some FAQs
 * on that tab."
 *
 * Two assertions, and they have to be made together. A test that only checked
 * the strings were gone would pass on a build that deleted them, and deleting a
 * true sentence is not the same as moving it. A test that only checked Help
 * carried them would pass on a build that said everything twice.
 *
 * **The sentence budget is the part that holds.** `quietScreen.test.tsx` counts
 * words, which stops the panel growing back in bulk; it does not stop one long
 * paragraph replacing three short ones. The rule here is structural: from the
 * top of the upload card to the last result row, no explanatory paragraph runs
 * to more than one sentence. A rule about sentences is a rule a pull request has
 * to argue with, which is what the word budget's own docstring says about
 * numbers in tests.
 *
 * What is exempt, and why, is listed on `EXEMPT` below. It is short and every
 * entry is something the brief names as staying exactly as it is.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { SingleLabelTab } from '../components/SingleLabelTab'
import {
  applicationDocument,
  classification,
  fileClassification,
  parsedField,
  verification,
} from './fixtures'
import type { VerificationResult } from '../types'

/**
 * The six strings the author asked for, verbatim from the released build.
 *
 * Whitespace is collapsed before comparing, because JSX wraps these across
 * lines and the rendered text joins them with single spaces.
 */
const REMOVED = [
  'One place for everything. PDFs and images, one file or several. We work out what each one is: ' +
    'an application tells us what the label should say, an image of the label shows us what it ' +
    'does say. An application that carries its own label artwork is enough on its own. Files are ' +
    'read here and are not sent to TTB or kept.',
  'Not compared against the label. It says which numeric rule to expect: the proof cross-check ' +
    'for spirits, range handling for wine.',
  'Upload something to turn on the check: the label application, an image of the label, or both.',
  'This shows the declared value appears on the label. It does not show it appears as the brand, ' +
    'in the required type size, or on the required panel (OOS-5).',
  'were read from the label artwork inside this application, not from its text.',
  'This application carries its own label artwork, so you do not have to add an image.',
]

function collapsed(text: string): string {
  return text.replace(/\s+/g, ' ').trim()
}

/**
 * A document-only submission whose parse leaves a class or type code and a
 * fanciful name, which is the shape that used to print two explanatory
 * paragraphs about values the check does not use.
 */
const DOCUMENT = applicationDocument({
  fields: [
    parsedField('brand_name', 'SIERRA VERDE', { source: 'embedded_text' }),
    parsedField('class_type', 'MEZCAL', { source: 'embedded_text' }),
    parsedField('alcohol_content', null),
    parsedField('net_contents', null),
    parsedField('beverage_type', null),
  ],
  fanciful_name: 'ROSA',
  class_type_code: '141',
  artwork_images_found: 1,
  artwork_images_read: 0,
  artwork_read: false,
  notes: [],
})

const CLASSIFIED = classification({
  files: [fileClassification('cola.pdf', 'application_document')],
  application_document: DOCUMENT,
  label_images: 0,
})

function result(): VerificationResult {
  return { ...verification(), application_document: DOCUMENT }
}

function stub() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      status: 200,
      json: async () => (url === '/api/classify' ? CLASSIFIED : result()),
    })),
  )
}

function pdf() {
  return new File([new Uint8Array([37, 80, 68, 70])], 'cola.pdf', { type: 'application/pdf' })
}

/** Upload a document and run the check, so the whole screen is on the page. */
async function checkedScreen() {
  const user = userEvent.setup()
  stub()
  render(<SingleLabelTab />)
  await user.upload(screen.getByLabelText('Files for this label'), pdf())
  await waitFor(() => expect(screen.getByText(/values were filled in/)).toBeInTheDocument())
  await user.click(screen.getByRole('button', { name: 'Check this label' }))
  await waitFor(() => expect(document.querySelector('.summary-line')).not.toBeNull())
}

async function helpPage() {
  const user = userEvent.setup()
  render(<App />)
  await user.click(screen.getByRole('tab', { name: 'Help' }))
  return screen.getByRole('tabpanel', { name: 'Help' })
}

afterEach(() => vi.unstubAllGlobals())

describe('the six strings are off the check screens', () => {
  it.each(REMOVED)('does not render %#', async (removed) => {
    await checkedScreen()

    expect(collapsed(document.body.textContent ?? '')).not.toContain(collapsed(removed))
  })

  it('replaces the empty-state prompt with a short label rather than nothing', async () => {
    // The agent still has to know why the button is inert.
    stub()
    render(<SingleLabelTab />)

    expect(screen.getByRole('button', { name: 'Check this label' })).toBeDisabled()
    expect(screen.getByText('Upload a file to check.')).toBeInTheDocument()
  })

  it('keeps the fanciful name as a line, not as a sentence', async () => {
    // The brief offered two options. This is the quieter one: the value is a
    // real thing the parser read off the document in front of the agent, so it
    // stays as a datum, and why it is not compared is a Help entry.
    await checkedScreen()

    expect(screen.getByText('Fanciful name')).toBeInTheDocument()
    expect(screen.getByText('ROSA')).toBeInTheDocument()
    expect(screen.queryByText(/It is not one of the fields we compare/)).not.toBeInTheDocument()
  })
})

describe('the Help tab carries what was taken off', () => {
  it('is the third segment of the existing tab set', async () => {
    render(<App />)
    const tabs = screen.getAllByRole('tab')

    expect(tabs.map((tab) => tab.textContent)).toEqual([
      'Check one label',
      'Check many labels',
      'Help',
    ])
  })

  it('answers what to upload, and that one file is enough', async () => {
    const help = await helpPage()

    expect(within(help).getByRole('heading', { name: 'What do I upload?' })).toBeInTheDocument()
    expect(within(help).getByText(/PDFs and images, one file or several/)).toBeInTheDocument()
    expect(within(help).getByText(/you do not have to add an image/)).toBeInTheDocument()
  })

  it('answers what each outcome means, including Contains', async () => {
    const help = await helpPage()

    for (const word of ['Match', 'Contains', 'Needs human review', 'Does not match', 'Not found']) {
      expect(within(help).getByText(word, { selector: 'dt' })).toBeInTheDocument()
    }
    // Contains is the one the author asked about, so its answer is asserted
    // rather than only its presence in the list.
    expect(
      within(help).getByText(/One thing was found, and it is the thing that had to be there/),
    ).toBeInTheDocument()
  })

  it('answers why a value can come from the artwork inside the application', async () => {
    const help = await helpPage()

    expect(
      within(help).getByRole('heading', {
        name: /Why does it sometimes say a value came from the label artwork/,
      }),
    ).toBeInTheDocument()
  })

  it('carries the limit of a search hit, which came off the results panel', async () => {
    const help = await helpPage()

    expect(
      within(help).getByRole('heading', { name: /not judged for type size or placement/ }),
    ).toBeInTheDocument()
    expect(within(help).getByText(/it is there as the brand/)).toBeInTheDocument()
  })

  it('answers why a bottle photo reads worse than filed artwork', async () => {
    const help = await helpPage()

    expect(
      within(help).getByRole('heading', { name: /Why can it not read a photo of a bottle/ }),
    ).toBeInTheDocument()
  })

  it('answers where beverage type comes from, including the rule it selects', async () => {
    const help = await helpPage()

    expect(
      within(help).getByRole('heading', { name: 'Where does beverage type come from?' }),
    ).toBeInTheDocument()
    expect(within(help).getByText(/range handling for wine/)).toBeInTheDocument()
  })

  it('says plainly that nothing is stored', async () => {
    const help = await helpPage()

    expect(
      within(help).getByRole('heading', { name: 'What happens to my files?' }),
    ).toBeInTheDocument()
    expect(within(help).getByText('Nothing is stored.')).toBeInTheDocument()
  })

  it('says what the tool is not, and who decides', async () => {
    const help = await helpPage()

    expect(
      within(help).getByRole('heading', { name: 'What is this tool not?' }),
    ).toBeInTheDocument()
    expect(within(help).getByText(/not an official TTB or Treasury system/)).toBeInTheDocument()
    expect(within(help).getByText(/It recommends and you decide/)).toBeInTheDocument()
  })

  it('names no requirement identifiers on the page', async () => {
    // The author's register, not the traceability matrix's. An agent reading
    // "OOS-5" learns nothing they can act on.
    const help = await helpPage()

    expect(help.textContent ?? '').not.toMatch(/\b(FR|NFR|OOS|ADR|OQ|US|SC|A)-\d/)
  })

  it('has no controls on it except links', async () => {
    const help = await helpPage()

    expect(within(help).queryAllByRole('button')).toHaveLength(0)
    expect(within(help).queryAllByRole('textbox')).toHaveLength(0)
    expect(within(help).queryAllByRole('combobox')).toHaveLength(0)
  })
})

/**
 * Paragraphs that are allowed more than one sentence, and why.
 *
 * Each of these is something the brief names as staying exactly as it is, or is
 * not an explanatory paragraph at all.
 */
const EXEMPT = [
  // FR-9's messages. "Cutting words is not licence to drop a message that names
  // a real problem." The brief names these as staying exactly as they are.
  'notice__headline',
  'notice__detail',
  /*
   * The government warning card's own detail: the capitalization verdict, the
   * diff legend NFR-5 requires beside a colour-coded difference, and the
   * bold-type note. The last is the API's own sentence reproduced verbatim so
   * that OOS-4 cannot drift between the server and this build, which
   * `ResultCard` says in as many words, and it is behind a subheading inside
   * one card rather than sitting on the screen.
   */
  'card__detail--note',
  'card__detail--fail',
  /*
   * "This tool recommends. You decide." Four words, two full stops, and the
   * whole of the tool's posture. `quietScreen.test.tsx` fails if it is removed.
   */
  'footnote',
]

describe('the check screen carries no paragraph longer than a sentence', () => {
  /**
   * Sentence-enders, counted on the rendered text.
   *
   * A full stop inside a decimal or an abbreviation would over-count, so the
   * pattern requires a space or the end of the string after it. This is a
   * heuristic and it is deliberately a strict one: a paragraph that trips it
   * because of an abbreviation is a paragraph that should have been shorter.
   */
  function sentences(text: string): number {
    return (collapsed(text).match(/[.?!](\s|$)/g) ?? []).length
  }

  it('holds from the top of the upload card to the last result row', async () => {
    await checkedScreen()

    const offenders = Array.from(document.querySelectorAll('p'))
      .filter((node) => !EXEMPT.some((className) => node.classList.contains(className)))
      .filter((node) => !node.closest('.visually-hidden'))
      .map((node) => collapsed(node.textContent ?? ''))
      .filter((text) => sentences(text) > 1)

    expect(offenders).toEqual([])
  })

  it('holds on the empty screen too, before anything is uploaded', async () => {
    stub()
    render(<SingleLabelTab />)

    const offenders = Array.from(document.querySelectorAll('p'))
      .filter((node) => !node.closest('.visually-hidden'))
      .map((node) => collapsed(node.textContent ?? ''))
      .filter((text) => sentences(text) > 1)

    expect(offenders).toEqual([])
  })
})
