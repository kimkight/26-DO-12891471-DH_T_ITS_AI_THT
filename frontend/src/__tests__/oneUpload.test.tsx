/**
 * One upload, sorted by the server (FR-12, ADR 0011, US-25).
 *
 * The author's words on 2026-08-29: "these should be combined; just one upload;
 * simplify the interface. You should be able to upload (pdfs or images)." So
 * there is one picker, it takes both, and the server decides what each file is
 * from the file rather than from which control it arrived in.
 *
 * These were the FR-11 upload tests. Everything they asserted about what a
 * parsed application does to the form is still asserted here, because none of
 * that changed; what changed is the control the file goes into and the endpoint
 * that sorts it.
 *
 * Requirements: FR-12 (one control, PDFs and images, classification reported
 * per file), FR-11 (the application as an input, precedence unchanged), FR-3
 * (the parsed values are surfaced for confirmation and the agent's correction
 * wins), FR-9 (an unreadable document names the problem and leaves the typed
 * path open), NFR-4, NFR-5 (labelled, keyboard reachable, announced with its
 * classification). Stories: US-23, US-25.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SingleLabelTab } from '../components/SingleLabelTab'
import {
  applicationDocument,
  classification,
  fileClassification,
  parsedField,
  verification,
} from './fixtures'
import type { ApplicationDocumentResult, ClassificationResult } from '../types'

function pdfFile(name = 'application.pdf') {
  return new File([new Uint8Array([37, 80, 68, 70])], name, { type: 'application/pdf' })
}

function pngFile(name = 'label.png') {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
}

/** The classification a single uploaded application produces. */
function documentOnly(document: ApplicationDocumentResult): ClassificationResult {
  return classification({
    files: [fileClassification('application.pdf', 'application_document')],
    application_document: document,
    label_images: 0,
  })
}

/** Route each request by URL, so one stub serves both endpoints. */
function stubApi(result: unknown, ok = true, status = 200) {
  const fetchMock = vi.fn(async (url: string) => {
    if (url === '/api/classify') {
      return { ok, status, json: async () => result } as Response
    }
    return { ok: true, status: 200, json: async () => verification() } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** Stub the classify call with a document, which is the ordinary case here. */
function stubDocument(document: ApplicationDocumentResult) {
  return stubApi(documentOnly(document))
}

async function attachApplication(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText('Files for this label'), pdfFile())
}

/**
 * Open the disclosure that holds the values that were read (US-26).
 *
 * After something has been processed the read values are summary lines and
 * their boxes are behind this control, collapsed. FR-3 keeps them editable; it
 * just stops them being in the way.
 */
async function reviewTheValues(user: ReturnType<typeof userEvent.setup>) {
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /Review the values/i })).toBeInTheDocument(),
  )
  await user.click(screen.getByRole('button', { name: /Review the values/i }))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

/** Every value present on TTB F 5100.31 and on a Registry printout. */
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

describe('one control for everything', () => {
  it('offers a single labelled picker on the same screen as the fields it replaces', () => {
    render(<SingleLabelTab />)
    expect(
      screen.getByRole('heading', {
        name: /Upload the label application, a photo of the label, or both/i,
      }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Files for this label')).toBeInTheDocument()
    // The two separate pickers are gone. That is the change.
    expect(screen.queryByLabelText('Label application')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Label image')).not.toBeInTheDocument()
  })

  it('accepts PDFs and images through that one control', () => {
    render(<SingleLabelTab />)
    const input = screen.getByLabelText('Files for this label')
    expect(input).toHaveAttribute(
      'accept',
      'application/pdf,image/jpeg,image/png,image/webp,image/tiff',
    )
    expect(input).toHaveAttribute('multiple')
  })

  it('says the files are read here and not sent to TTB', () => {
    render(<SingleLabelTab />)
    expect(screen.getByText(/not sent to TTB or kept/i)).toBeInTheDocument()
  })

  it('sends what was uploaded to the classify endpoint, not to the check', async () => {
    const user = userEvent.setup()
    const fetchMock = stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(fetchMock.mock.calls[0][0]).toBe('/api/classify')
  })

  it('shows what each file was taken to be, so a wrong call is visible', async () => {
    const user = userEvent.setup()
    stubApi(
      classification({
        files: [
          fileClassification('application.pdf', 'application_document'),
          fileClassification('label.png'),
        ],
        application_document: FULL_DOCUMENT,
        label_images: 1,
      }),
    )
    render(<SingleLabelTab />)

    await user.upload(screen.getByLabelText('Files for this label'), [pdfFile(), pngFile()])

    await waitFor(() => expect(screen.getByText('Label application')).toBeInTheDocument())
    expect(screen.getByText('Label picture')).toBeInTheDocument()
    expect(
      screen.getByText('This is a PDF, so we read it as the label application.'),
    ).toBeInTheDocument()
    expect(screen.getByText('We read this picture as a label.')).toBeInTheDocument()
  })

  it('turns the check on as soon as anything is uploaded, with no photo required', async () => {
    const user = userEvent.setup()
    stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    expect(screen.getByRole('button', { name: 'Check this label' })).toBeDisabled()

    await attachApplication(user)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Check this label' })).toBeEnabled(),
    )
  })
})

describe('what the parsed values do to the form', () => {
  it('fills every field the document supplied', async () => {
    const user = userEvent.setup()
    stubDocument(FULL_DOCUMENT)
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
    stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    // The four compared values. The beverage type is a select rather than a
    // text field and carries its own line (US-26).
    await waitFor(() =>
      expect(screen.getAllByText(/Read from the application form/i)).toHaveLength(4),
    )
  })

  it('binds the mark to its input so a screen reader reads it out', async () => {
    const user = userEvent.setup()
    stubDocument(FULL_DOCUMENT)
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
    stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await reviewTheValues(user)
    const brand = await screen.findByLabelText('Brand name')
    await waitFor(() => expect(brand).toHaveValue("STONE'S THROW"))
    await user.clear(brand)
    await user.type(brand, 'Stone Throw')
    expect(brand).toHaveValue('Stone Throw')
  })

  it('drops the mark from a field the agent edits', async () => {
    const user = userEvent.setup()
    stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await reviewTheValues(user)
    const brand = await screen.findByLabelText('Brand name')
    await waitFor(() => expect(brand).toHaveValue("STONE'S THROW"))
    await user.type(brand, 'X')
    await waitFor(() =>
      expect(screen.getAllByText(/Read from the application form/i)).toHaveLength(3),
    )
  })

  it('checks the label with what is in the fields, not with the document', async () => {
    const user = userEvent.setup()
    const fetchMock = stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await reviewTheValues(user)
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))
    const brand = screen.getByLabelText('Brand name')
    await user.clear(brand)
    await user.type(brand, 'Corrected Brand')
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url]) => url === '/api/verify')).toBe(true),
    )
    const call = fetchMock.mock.calls.find(([url]) => url === '/api/verify') as unknown as [
      string,
      RequestInit,
    ]
    expect((call[1].body as FormData).get('brand_name')).toBe('Corrected Brand')
    // And the file itself still goes with the check, because the label side may
    // be the artwork inside it (ADR 0010).
    expect((call[1].body as FormData).getAll('files')).toHaveLength(1)
  })
})

describe('what the form does not carry', () => {
  it('names the values the agent still has to enter, and why', async () => {
    const user = userEvent.setup()
    stubDocument(applicationDocument())
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() =>
      expect(
        screen.getByText(/Not on this application, so you will need to enter/i),
      ).toBeInTheDocument(),
    )
    expect(
      screen.getByText(/class or type designation is not an item on TTB F 5100.31/i),
    ).toBeInTheDocument()
  })

  it('leaves a value the document did not carry blank rather than guessing', async () => {
    const user = userEvent.setup()
    stubDocument(applicationDocument())
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))
    expect(screen.getByLabelText('Alcohol content')).toHaveValue('')
    expect(screen.getByLabelText('Net contents')).toHaveValue('')
  })

  it("says how the document was read, in the agent's words", async () => {
    const user = userEvent.setup()
    stubDocument(applicationDocument({ extraction_path: 'ocr', pages_read: 2 }))
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() =>
      expect(screen.getByText(/as pictures, the way we read a label photo/i)).toBeInTheDocument(),
    )
  })

  it('reports the class or type code without comparing it', async () => {
    const user = userEvent.setup()
    stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByText(/class or type code as 141/i)).toBeInTheDocument())
  })
})

describe('when the document cannot be read (FR-9)', () => {
  /*
   * The classification still stands: the file is a PDF and was read as the
   * application side. What failed is opening it. So the classify call succeeds
   * and carries the failure in `application_error`, which is the honest shape:
   * "we know what this is and we could not read it" is a different thing for an
   * agent to act on than "we do not know what this is".
   */
  const UNREADABLE = classification({
    files: [fileClassification('application.pdf', 'application_document')],
    application_document: null,
    label_images: 0,
    application_error: {
      code: 'unreadable_application_document',
      message: 'The uploaded file could not be opened as a PDF.',
      limit: null,
    },
  })

  it('names the problem and leaves the typed path open', async () => {
    const user = userEvent.setup()
    stubApi(UNREADABLE)
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
    stubApi(UNREADABLE)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
    expect(screen.getByLabelText('Brand name')).toHaveValue('')
    expect(screen.queryByText(/Read from the application form/i)).not.toBeInTheDocument()
  })

  it('interrupts, because it replaces what the agent was waiting for', async () => {
    const user = userEvent.setup()
    stubApi(UNREADABLE)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})

describe('announcements and keyboard use (NFR-5)', () => {
  it('announces what was filled in, and how many', async () => {
    const user = userEvent.setup()
    stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    const region = screen.getByLabelText('Your uploads')
    await waitFor(() => expect(region).toHaveTextContent(/5 of 5 values filled in/i))
    expect(region).toHaveTextContent(/Check them and change anything that is wrong/i)
  })

  it('announces into its own region, not the one the result uses', async () => {
    const user = userEvent.setup()
    stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() =>
      expect(screen.getByLabelText('Your uploads')).toHaveTextContent(/filled in/i),
    )
    expect(screen.getByLabelText('Check result')).toHaveTextContent('')
  })

  it('offers a control to take each file back off, which clears the marks', async () => {
    const user = userEvent.setup()
    stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() =>
      expect(screen.getAllByText(/Read from the application form/i)).toHaveLength(4),
    )
    await user.click(screen.getByRole('button', { name: 'Remove application.pdf' }))
    await waitFor(() =>
      expect(screen.queryByText(/Read from the application form/i)).not.toBeInTheDocument(),
    )
    // The values stay: removing the file is not an instruction to discard what
    // it already put in the fields.
    expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW")
  })

  it('names every file it accepted, with what it was taken to be', async () => {
    const user = userEvent.setup()
    stubDocument(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)

    await waitFor(() =>
      expect(screen.getByLabelText('Your uploads')).toHaveTextContent(
        /application\.pdf, read as a label application/i,
      ),
    )
  })
})
