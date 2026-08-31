/**
 * The application values, quiet by default and loud only about gaps (US-26).
 *
 * The author's instruction on 2026-08-29: "Collapse the form fields and only
 * expand if there is something that isn't read in from the application or
 * picture."
 *
 * Session 10 collapsed the five typed fields behind a disclosure, which fixed
 * what greeted an agent on load. This is about what happens after something has
 * been processed: a value the tool has already read should not come back as an
 * empty-looking box, and a value it could not read should be the only thing on
 * screen that looks like work.
 *
 * Requirements: FR-13 (this behaviour), FR-11 (the application as the input,
 * precedence unchanged), FR-3 (every value stays the agent's to correct),
 * FR-2 (an empty field is not compared, so leaving a gap empty is legitimate),
 * NFR-4, NFR-5 (focus, announcement, and nothing hidden from assistive
 * technology that is not also hidden visually). Story: US-26.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SingleLabelTab } from '../components/SingleLabelTab'
import { gapAnnouncement, gapReason } from '../lib/applicationFields'
import {
  applicationDocument,
  classification,
  fileClassification,
  parsedField,
  verification,
} from './fixtures'
import type { ApplicationDocumentResult } from '../types'

afterEach(() => {
  vi.unstubAllGlobals()
})

function pdfFile(name = 'application.pdf') {
  return new File([new Uint8Array([37, 80, 68, 70])], name, { type: 'application/pdf' })
}

function stub(document: ApplicationDocumentResult) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) =>
      url === '/api/classify'
        ? ({
            ok: true,
            status: 200,
            json: async () =>
              classification({
                files: [fileClassification('application.pdf', 'application_document')],
                application_document: document,
                label_images: 0,
              }),
          } as Response)
        : ({ ok: true, status: 200, json: async () => verification() } as Response),
    ),
  )
}

async function upload(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText('Files for this label'), pdfFile())
}

/** Every compared value present, so there is nothing left to enter. */
const NO_GAPS = applicationDocument({
  fields: [
    parsedField('brand_name', "STONE'S THROW"),
    parsedField('class_type', 'KENTUCKY STRAIGHT BOURBON WHISKEY'),
    parsedField('alcohol_content', '45% ALC/VOL'),
    parsedField('net_contents', '750 ML'),
    parsedField('beverage_type', 'distilled spirits'),
  ],
  notes: [],
})

/** One compared value missing, which is the case the disclosure exists for. */
const ONE_GAP = applicationDocument({
  fields: [
    parsedField('brand_name', "STONE'S THROW"),
    parsedField('class_type', 'KENTUCKY STRAIGHT BOURBON WHISKEY'),
    parsedField('alcohol_content', null),
    parsedField('net_contents', '750 ML'),
    parsedField('beverage_type', 'distilled spirits'),
  ],
  notes: ['The alcohol content is not an item on TTB F 5100.31 (04/2023).'],
})

/** The author's own case: the artwork inside the document answered two of them. */
const FROM_ARTWORK = applicationDocument({
  fields: [
    parsedField('brand_name', 'DEL MAGUEY'),
    parsedField('class_type', 'MEZCAL', { source: 'embedded_artwork' }),
    parsedField('alcohol_content', '42% ALC BY VOL', { source: 'embedded_artwork' }),
    parsedField('net_contents', '750 ML', { source: 'embedded_artwork' }),
    parsedField('beverage_type', null),
  ],
  artwork_images_found: 1,
  artwork_images_read: 1,
  label_artwork_available: true,
  notes: [],
})

describe('before anything has been uploaded', () => {
  it('keeps the Session 10 default: one collapsed disclosure, no summary lines', () => {
    render(<SingleLabelTab />)

    const toggle = screen.getByRole('button', { name: /Or type the application values/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.getByLabelText('Brand name')).not.toBeVisible()
    expect(screen.queryByText('Read from your upload')).not.toBeInTheDocument()
  })
})

describe('when everything was read', () => {
  it('shows no editable field at all', async () => {
    const user = userEvent.setup()
    stub(NO_GAPS)
    render(<SingleLabelTab />)

    await upload(user)

    await waitFor(() => expect(screen.getByText('Read from your upload')).toBeVisible())
    for (const label of [
      'Brand name',
      'Class or type designation',
      'Alcohol content',
      'Net contents',
      'Beverage type',
    ]) {
      expect(screen.getByLabelText(label)).not.toBeVisible()
    }
  })

  it('holds them behind one collapsed disclosure called "Review the values"', async () => {
    const user = userEvent.setup()
    stub(NO_GAPS)
    render(<SingleLabelTab />)

    await upload(user)

    const toggle = await screen.findByRole('button', { name: /Review the values/i })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    // And it is still the agent's to change, which is FR-3.
    await user.click(toggle)
    expect(screen.getByLabelText('Alcohol content')).toBeVisible()
  })

  it('shows each value as a line with where it came from', async () => {
    const user = userEvent.setup()
    stub(NO_GAPS)
    render(<SingleLabelTab />)

    await upload(user)

    await waitFor(() => expect(screen.getByText("STONE'S THROW")).toBeVisible())
    expect(screen.getByText('45% ALC/VOL')).toBeVisible()
    expect(screen.getAllByText('Application form').length).toBe(5)
  })

  it('says nothing in the live region, because there is nothing to say', async () => {
    const user = userEvent.setup()
    stub(NO_GAPS)
    render(<SingleLabelTab />)

    await upload(user)

    await waitFor(() => expect(screen.getByText('Read from your upload')).toBeVisible())
    expect(screen.getByLabelText('Application values')).toHaveTextContent('')
  })
})

describe('when one value was not read', () => {
  it('shows exactly one editable field, and puts focus on it', async () => {
    const user = userEvent.setup()
    stub(ONE_GAP)
    render(<SingleLabelTab />)

    await upload(user)

    await waitFor(() => expect(screen.getByLabelText('Alcohol content')).toBeVisible())
    expect(screen.getByLabelText('Alcohol content')).toHaveFocus()
    // The other three were read, so their boxes are behind the disclosure.
    for (const label of ['Brand name', 'Class or type designation', 'Net contents']) {
      expect(screen.getByLabelText(label)).not.toBeVisible()
    }
  })

  it('announces which value is missing and what to do about it', async () => {
    const user = userEvent.setup()
    stub(ONE_GAP)
    render(<SingleLabelTab />)

    await upload(user)

    await waitFor(() =>
      expect(screen.getByLabelText('Application values')).toHaveTextContent(
        'Alcohol content was not found in your upload. Enter it, or upload a clearer image.',
      ),
    )
  })

  it('names the section for what is left rather than for what was done', async () => {
    const user = userEvent.setup()
    stub(ONE_GAP)
    render(<SingleLabelTab />)

    await upload(user)

    await waitFor(() => expect(screen.getByText('One value was not read')).toBeVisible())
  })

  it('keeps the gap field where it is while the agent clears and retypes', async () => {
    /*
     * The two sections are decided when the upload is read, not from what is
     * currently in the boxes. A field that moved between them as the agent
     * typed would remount under them and drop focus after the first keystroke.
     */
    const user = userEvent.setup()
    stub(ONE_GAP)
    render(<SingleLabelTab />)
    await upload(user)
    const field = await screen.findByLabelText('Alcohol content')

    await user.type(field, '42%')
    await user.clear(field)
    await user.type(field, '45%')

    expect(field).toHaveValue('45%')
    expect(field).toBeVisible()
  })
})

describe('the source of a value that was read', () => {
  it('distinguishes the document text from the artwork inside it', async () => {
    const user = userEvent.setup()
    stub(FROM_ARTWORK)
    render(<SingleLabelTab />)

    await upload(user)

    await waitFor(() => expect(screen.getByText('DEL MAGUEY')).toBeVisible())
    expect(screen.getByText('Application form')).toBeVisible()
    expect(screen.getAllByText('Label artwork in the application')).toHaveLength(3)
    // The chip is the whole of it. The sentence that used to sit under each
    // value said the same thing at length, and the upload card says it once
    // above (2026-08-31); see quietScreen.test.tsx for the budget that keeps it
    // from coming back.
    expect(screen.queryAllByText(/not from its text/i)).toHaveLength(1)
  })
})

describe('beverage type keeps its own line (ADR 0008, ADR 0016)', () => {
  it('states why the boxes did not settle it, with the selector inline', async () => {
    const user = userEvent.setup()
    stub(FROM_ARTWORK)
    render(<SingleLabelTab />)

    await upload(user)

    await waitFor(() => expect(screen.getByLabelText('Beverage type')).toBeVisible())
    expect(screen.getByLabelText('Beverage type')).toHaveAccessibleDescription(
      /item 5\u2019s boxes were read from the page and none of them stood out/i,
    )
  })

  it('never takes focus, because it is never compared', async () => {
    const user = userEvent.setup()
    stub(ONE_GAP)
    render(<SingleLabelTab />)

    await upload(user)

    await waitFor(() => expect(screen.getByLabelText('Alcohol content')).toHaveFocus())
    expect(screen.getByLabelText('Beverage type')).not.toHaveFocus()
  })

  it('is a summary line when the document did state it', async () => {
    const user = userEvent.setup()
    stub(NO_GAPS)
    render(<SingleLabelTab />)

    await upload(user)

    await waitFor(() => expect(screen.getByText('distilled spirits')).toBeVisible())
    expect(screen.getByLabelText('Beverage type')).not.toBeVisible()
  })
})

describe('the sentences themselves', () => {
  it('names the field and both ways out of the gap', () => {
    expect(gapReason('Alcohol content')).toBe(
      'Alcohol content was not found in your upload. Enter it, or upload a clearer image.',
    )
  })

  it('reads as English when more than one value is missing', () => {
    expect(gapAnnouncement(['alcohol content', 'net contents'])).toBe(
      'Alcohol content and net contents were not found in your upload. Enter them, or upload a clearer image.',
    )
    expect(gapAnnouncement([])).toBe('')
  })
})
