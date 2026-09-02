/**
 * What the agent typed survives what the document says, and a photograph alone
 * asks for nothing (v1.3.0; code review findings 6, 19 and 29; #105, #118).
 *
 * The rule, from FR-11: a typed value wins. Until v1.3.0 the source map was
 * rebuilt from the document, so a value typed before the upload became
 * "absent" when the document did not carry that field: it stayed in the box,
 * the screen said "Not supplied" beside it, and the request omitted it. Now
 * agent input wins over absence, and where the document genuinely disagrees
 * the disagreement is shown and the agent's value is used.
 *
 * Requirements: FR-11 (precedence), FR-2 (a blank is not compared), FR-4
 * (case is not a disagreement), FR-13, NFR-4, NFR-5.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SingleLabelTab } from '../components/SingleLabelTab'
import { PHOTO_ONLY_NOTE } from '../lib/uploadAnnouncement'
import {
  applicationDocument,
  classification,
  fileClassification,
  parsedField,
  verification,
} from './fixtures'
import type { ApplicationDocumentResult, ClassificationResult } from '../types'

const TOGGLE = 'Or type the application values'
const REVIEW = 'Review the values'

function pdfFile(name = 'application.pdf') {
  return new File([new Uint8Array([37, 80, 68, 70])], name, { type: 'application/pdf' })
}

function pngFile(name = 'label.png') {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
}

function documentOnly(document: ApplicationDocumentResult): ClassificationResult {
  return classification({
    files: [fileClassification('application.pdf', 'application_document')],
    application_document: document,
    label_images: 0,
  })
}

function stubApi(classified: ClassificationResult) {
  const fetchMock = vi.fn(async (url: string) => {
    if (url === '/api/classify') return { ok: true, status: 200, json: async () => classified }
    return { ok: true, status: 200, json: async () => verification() } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** A document that carries everything but the brand name. */
const BRANDLESS = applicationDocument({
  fields: [
    parsedField('brand_name', null),
    parsedField('class_type', 'KENTUCKY STRAIGHT BOURBON WHISKEY'),
    parsedField('alcohol_content', '45% ALC/VOL'),
    parsedField('net_contents', '750 ML'),
    parsedField('beverage_type', 'distilled spirits'),
  ],
  notes: [],
})

/** A document that carries every value, with a brand of its own. */
const FULL = applicationDocument({
  fields: [
    parsedField('brand_name', "STONE'S THROW"),
    parsedField('class_type', 'KENTUCKY STRAIGHT BOURBON WHISKEY'),
    parsedField('alcohol_content', '45% ALC/VOL'),
    parsedField('net_contents', '750 ML'),
    parsedField('beverage_type', 'distilled spirits'),
  ],
  notes: [],
})

async function typeBrand(user: ReturnType<typeof userEvent.setup>, value: string) {
  await user.click(screen.getByRole('button', { name: TOGGLE }))
  await user.type(screen.getByLabelText('Brand name'), value)
}

async function uploadApplication(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText('Files for this label'), pdfFile())
  await waitFor(() => expect(screen.getByText('Read from your upload')).toBeVisible())
}

/** Run the check and return the multipart body the browser sent. */
async function checkedBody(
  user: ReturnType<typeof userEvent.setup>,
  fetchMock: ReturnType<typeof vi.fn>,
): Promise<FormData> {
  await user.click(screen.getByRole('button', { name: 'Check this label' }))
  await waitFor(() =>
    expect(fetchMock.mock.calls.some(([url]) => url === '/api/verify')).toBe(true),
  )
  const call = fetchMock.mock.calls.find(([url]) => url === '/api/verify') as unknown as [
    string,
    RequestInit,
  ]
  return call[1].body as FormData
}

afterEach(() => vi.unstubAllGlobals())

describe('agent input wins over absence (finding 6)', () => {
  it('keeps a typed value when the document uploaded afterwards lacks that field', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi(documentOnly(BRANDLESS))
    render(<SingleLabelTab />)
    await typeBrand(user, 'Grey Harbor')

    await uploadApplication(user)

    // The value is still in the box, still the agent's, and not asked for.
    expect(screen.getByLabelText('Brand name')).toHaveValue('Grey Harbor')
    expect(screen.getByText('Grey Harbor')).toBeVisible()
    expect(screen.getByText('You typed this')).toBeVisible()
    expect(screen.queryByText('Not supplied')).not.toBeInTheDocument()
    expect(screen.queryByText(/value was not read|values were not read/)).not.toBeInTheDocument()

    // And the check uses it.
    const body = await checkedBody(user, fetchMock)
    expect(body.get('brand_name')).toBe('Grey Harbor')
  })

  it('shows a disagreement when the document carries a different value, and uses the typed one', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi(documentOnly(FULL))
    render(<SingleLabelTab />)
    await typeBrand(user, 'Grey Harbor')

    await uploadApplication(user)

    const notes = screen.getAllByText(
      /The application you uploaded says "STONE'S THROW"; the check uses your value/,
    )
    expect(notes[0]).toBeVisible()
    expect(screen.getByLabelText('Brand name')).toHaveValue('Grey Harbor')
    // The other four still came from the document.
    expect(screen.getAllByText('Application form').length).toBeGreaterThanOrEqual(3)

    const body = await checkedBody(user, fetchMock)
    expect(body.get('brand_name')).toBe('Grey Harbor')
  })

  it('does not call a difference of case a disagreement (FR-4)', async () => {
    const user = userEvent.setup()
    stubApi(documentOnly(FULL))
    render(<SingleLabelTab />)
    await typeBrand(user, "stone's throw")

    await uploadApplication(user)

    expect(screen.queryByText(/The application you uploaded says/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Brand name')).toHaveValue("stone's throw")
  })

  it('settles the disagreement once the agent edits the box', async () => {
    const user = userEvent.setup()
    stubApi(documentOnly(FULL))
    render(<SingleLabelTab />)
    await typeBrand(user, 'Grey Harbor')
    await uploadApplication(user)
    await waitFor(() =>
      expect(screen.getAllByText(/The application you uploaded says/).length).toBeGreaterThan(0),
    )

    await user.click(screen.getByRole('button', { name: REVIEW }))
    await user.type(screen.getByLabelText('Brand name'), ' Ltd')

    expect(screen.queryByText(/The application you uploaded says/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Brand name')).toHaveValue('Grey Harbor Ltd')
  })

  it('still fills a box the agent left empty', async () => {
    const user = userEvent.setup()
    stubApi(documentOnly(FULL))
    render(<SingleLabelTab />)
    await typeBrand(user, 'Grey Harbor')

    await uploadApplication(user)

    expect(screen.getByLabelText('Net contents')).toHaveValue('750 ML')
    expect(screen.getByLabelText('Class or type designation')).toHaveValue(
      'KENTUCKY STRAIGHT BOURBON WHISKEY',
    )
  })
})

describe('a blanked document value is left out of the check (finding 29)', () => {
  it('sends the blank as an instruction the server honours', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi(documentOnly(FULL))
    render(<SingleLabelTab />)
    await uploadApplication(user)
    await user.click(screen.getByRole('button', { name: REVIEW }))
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))

    await user.clear(screen.getByLabelText('Brand name'))

    const body = await checkedBody(user, fetchMock)
    expect(body.get('brand_name')).toBe('')
    expect(body.getAll('cleared_fields')).toEqual(['brand_name'])
  })

  it('withdraws the instruction when a value is typed back', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi(documentOnly(FULL))
    render(<SingleLabelTab />)
    await uploadApplication(user)
    await user.click(screen.getByRole('button', { name: REVIEW }))
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))
    await user.clear(screen.getByLabelText('Brand name'))

    await user.type(screen.getByLabelText('Brand name'), 'Grey Harbor')

    const body = await checkedBody(user, fetchMock)
    expect(body.get('brand_name')).toBe('Grey Harbor')
    expect(body.getAll('cleared_fields')).toEqual([])
  })

  it('says what a blank does, in the hint above the boxes', async () => {
    const user = userEvent.setup()
    stubApi(documentOnly(FULL))
    render(<SingleLabelTab />)
    await user.click(screen.getByRole('button', { name: TOGGLE }))

    expect(screen.getByText(/a box you leave or make empty is left out of the check/)).toBeVisible()
  })
})

describe('a photograph alone (finding 19)', () => {
  const PHOTO_ONLY = classification({
    files: [fileClassification('label.png')],
    application_document: null,
    label_images: 1,
  })

  it('opens no box, moves no focus, and says the true thing', async () => {
    const user = userEvent.setup()
    stubApi(PHOTO_ONLY)
    render(<SingleLabelTab />)

    await user.upload(screen.getByLabelText('Files for this label'), pngFile())
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Check this label' })).toBeEnabled(),
    )

    // No gap section, no box, and the disclosure is still closed.
    expect(screen.queryByText(/value was not read|values were not read/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Brand name')).not.toBeVisible()
    expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'false')
    // Focus was not moved into a field.
    expect(document.activeElement).not.toBe(screen.getByLabelText('Brand name'))
    expect(document.activeElement).not.toBe(screen.getByLabelText('Class or type designation'))
    // The true sentence, on screen and in the uploads region; the wrong one nowhere.
    expect(screen.getByText(PHOTO_ONLY_NOTE)).toBeVisible()
    expect(screen.getByLabelText('Your uploads')).toHaveTextContent(PHOTO_ONLY_NOTE)
    expect(screen.queryByText(/upload a clearer image/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Application values')).toHaveTextContent('')
  })

  it('keeps a value the agent typed before choosing the photograph', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi(PHOTO_ONLY)
    render(<SingleLabelTab />)
    await typeBrand(user, 'Grey Harbor')

    await user.upload(screen.getByLabelText('Files for this label'), pngFile())
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Check this label' })).toBeEnabled(),
    )

    expect(screen.getByLabelText('Brand name')).toHaveValue('Grey Harbor')
    const body = await checkedBody(user, fetchMock)
    expect(body.get('brand_name')).toBe('Grey Harbor')
  })
})
