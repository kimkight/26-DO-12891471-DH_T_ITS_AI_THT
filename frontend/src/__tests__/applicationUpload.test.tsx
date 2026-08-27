/**
 * Uploading the label application instead of typing it (FR-11, ADR 0008).
 *
 * Requirements: FR-11 (the application is accepted as an alternative to typing
 * the same values), FR-3 (the parsed values are surfaced for confirmation and
 * the agent's correction wins), FR-9 (an unreadable document names the problem
 * and leaves the typed path open), NFR-4 (the alternative is on the same screen
 * as the fields it replaces), NFR-5 (labelled, keyboard reachable, announced).
 * Story: US-23.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SingleLabelTab } from '../components/SingleLabelTab'
import { applicationDocument, parsedField, verification } from './fixtures'

function pdfFile(name = 'application.pdf') {
  return new File([new Uint8Array([37, 80, 68, 70])], name, { type: 'application/pdf' })
}

function pngFile(name = 'label.png') {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
}

/** Route each request by URL, so one stub serves both endpoints. */
function stubApi(document: unknown, ok = true, status = 200) {
  const fetchMock = vi.fn(async (url: string) => {
    if (url === '/api/read-application') {
      return { ok, status, json: async () => document } as Response
    }
    return { ok: true, status: 200, json: async () => verification() } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function attachApplication(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText('Label application'), pdfFile())
}

afterEach(() => {
  vi.unstubAllGlobals()
})

const FULL_DOCUMENT = applicationDocument({
  fields: [
    parsedField('brand_name', "STONE'S THROW"),
    parsedField('class_type', 'KENTUCKY STRAIGHT BOURBON WHISKEY'),
    parsedField('alcohol_content', '45% ALC/VOL'),
    parsedField('net_contents', '750 ML'),
    parsedField('beverage_type', 'distilled spirits'),
  ],
  class_type_code: '141',
  notes: [],
})

describe('the alternative to typing the application values', () => {
  it('offers the upload on the same screen as the fields it replaces', () => {
    render(<SingleLabelTab />)
    expect(
      screen.getByRole('heading', { name: /Upload the label application/i }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Label application')).toBeInTheDocument()
  })

  it('says the file is read here and not sent to TTB', () => {
    render(<SingleLabelTab />)
    expect(screen.getByText(/not sent to TTB or kept/i)).toBeInTheDocument()
  })

  it('sends the document to the read endpoint, not to the check', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(fetchMock.mock.calls[0][0]).toBe('/api/read-application')
  })
})

describe('what the parsed values do to the form', () => {
  it('fills every field the document supplied', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))
    expect(screen.getByLabelText('Class or type designation')).toHaveValue(
      'KENTUCKY STRAIGHT BOURBON WHISKEY',
    )
    expect(screen.getByLabelText('Alcohol content')).toHaveValue('45% ALC/VOL')
    expect(screen.getByLabelText('Net contents')).toHaveValue('750 ML')
    expect(screen.getByLabelText('Beverage type')).toHaveValue('distilled spirits')
  })

  it('marks each filled field as read from the application form', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() =>
      expect(screen.getAllByText(/Read from the application form/i)).toHaveLength(5),
    )
  })

  it('binds the mark to its input so a screen reader reads it out', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() =>
      expect(screen.getByLabelText('Brand name')).toHaveAccessibleDescription(
        /Read from the application form/i,
      ),
    )
  })

  it('leaves every filled field editable, and the edit wins', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    const brand = await screen.findByLabelText('Brand name')
    await waitFor(() => expect(brand).toHaveValue("STONE'S THROW"))
    await user.clear(brand)
    await user.type(brand, 'Stone Throw')
    expect(brand).toHaveValue('Stone Throw')
  })

  it('drops the mark from a field the agent edits', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    const brand = await screen.findByLabelText('Brand name')
    await waitFor(() => expect(brand).toHaveValue("STONE'S THROW"))
    await user.type(brand, 'X')
    await waitFor(() =>
      expect(screen.getAllByText(/Read from the application form/i)).toHaveLength(4),
    )
  })

  it('checks the label with what is in the fields, not with the document', async () => {
    const user = userEvent.setup()
    const fetchMock = stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))
    const brand = screen.getByLabelText('Brand name')
    await user.clear(brand)
    await user.type(brand, 'Corrected Brand')
    await user.upload(screen.getByLabelText('Label image'), pngFile())
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const [url, init] = fetchMock.mock.calls[1] as unknown as [string, RequestInit]
    expect(url).toBe('/api/verify')
    expect((init.body as FormData).get('brand_name')).toBe('Corrected Brand')
  })
})

describe('what the form does not carry', () => {
  it('names the values the agent still has to enter, and why', async () => {
    const user = userEvent.setup()
    stubApi(applicationDocument())
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() =>
      expect(screen.getByText(/Not on this form, so you will need to enter/i)).toBeInTheDocument(),
    )
    expect(
      screen.getByText(/class or type designation is not an item on TTB F 5100.31/i),
    ).toBeInTheDocument()
  })

  it('leaves a value the document did not carry blank rather than guessing', async () => {
    const user = userEvent.setup()
    stubApi(applicationDocument())
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))
    expect(screen.getByLabelText('Alcohol content')).toHaveValue('')
    expect(screen.getByLabelText('Net contents')).toHaveValue('')
  })

  it("says how the document was read, in the agent's words", async () => {
    const user = userEvent.setup()
    stubApi(applicationDocument({ extraction_path: 'ocr', pages_read: 2 }))
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() =>
      expect(screen.getByText(/as pictures, the way we read a label photo/i)).toBeInTheDocument(),
    )
  })

  it('reports the class or type code without comparing it', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByText(/class or type code as 141/i)).toBeInTheDocument())
  })
})

describe('when the document cannot be read (FR-9)', () => {
  const ERROR_BODY = {
    error: {
      code: 'unreadable_application_document',
      message: 'The uploaded file could not be opened as a PDF.',
      limit: null,
    },
  }

  it('names the problem and leaves the typed path open', async () => {
    const user = userEvent.setup()
    stubApi(ERROR_BODY, false, 422)
    render(<SingleLabelTab />)
    await attachApplication(user)
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/couldn't read that label application/i)
    expect(alert).toHaveTextContent(/type the values in yourself/i)
    // The API's own message is kept underneath, because it names what was
    // actually wrong with the file.
    expect(alert).toHaveTextContent(/could not be opened as a PDF/i)
    expect(screen.getByLabelText('Brand name')).toBeEnabled()
  })

  it('fills nothing in from a document it could not read', async () => {
    const user = userEvent.setup()
    stubApi(ERROR_BODY, false, 422)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByLabelText('Brand name')).toHaveValue('')
    expect(screen.queryByText(/Read from the application form/i)).not.toBeInTheDocument()
  })

  it('interrupts, because it replaces what the agent was waiting for', async () => {
    const user = userEvent.setup()
    stubApi(ERROR_BODY, false, 422)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})

describe('announcements and keyboard use (NFR-5)', () => {
  it('announces what was filled in, and how many', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    const region = screen.getByLabelText('Application form')
    await waitFor(() => expect(region).toHaveTextContent(/5 of 5 values filled in/i))
    expect(region).toHaveTextContent(/Check them and change anything that is wrong/i)
  })

  it('announces into its own region, not the one the result uses', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() =>
      expect(screen.getByLabelText('Application form')).toHaveTextContent(/filled in/i),
    )
    expect(screen.getByLabelText('Check result')).toHaveTextContent('')
  })

  it('offers a control to take the document back off, which clears the marks', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() =>
      expect(screen.getAllByText(/Read from the application form/i)).toHaveLength(5),
    )
    await user.click(screen.getByRole('button', { name: 'Remove this application form' }))
    await waitFor(() =>
      expect(screen.queryByText(/Read from the application form/i)).not.toBeInTheDocument(),
    )
    // The values stay: removing the document is not an instruction to discard
    // what it already put in the fields.
    expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW")
  })

  it('accepts a PDF or an image of the form', () => {
    render(<SingleLabelTab />)
    expect(screen.getByLabelText('Label application')).toHaveAttribute(
      'accept',
      'application/pdf,image/jpeg,image/png,image/webp,image/tiff',
    )
  })
})
