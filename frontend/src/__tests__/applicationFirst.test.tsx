/**
 * The application document first, the typed fields behind a disclosure (US-24).
 *
 * The author's question, from using the deployed prototype: when would the
 * typed fields actually be used? Almost never as a starting point, because the
 * normal case is an agent holding the COLA document. So the document is the
 * primary application-side input and the five boxes are a confirmation surface.
 *
 * These tests pin the collapsed default and the three cases, and only the three
 * cases, in which the boxes open on their own.
 *
 * Requirements: FR-11 (the application as an input, precedence unchanged),
 * FR-2 (an empty field is not compared, so a collapsed field is a legitimate
 * submission), FR-9 (an unreadable document leaves the typed path open),
 * NFR-4 (fewer things in the way of the primary task), NFR-5 (keyboard
 * reachable, correct expanded state, auto-expansion announced).
 * Story: US-24.
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

const TOGGLE = /Or type the application values/i
/** What the same disclosure is called once something has been read (US-26). */
const REVIEW = /Review the values/i

function pdfFile(name = 'application.pdf') {
  return new File([new Uint8Array([37, 80, 68, 70])], name, { type: 'application/pdf' })
}

/** Route each request by URL, so one stub serves both endpoints (FR-12). */
function stubApi(document: unknown, ok = true, status = 200) {
  const fetchMock = vi.fn(async (url: string) => {
    if (url === '/api/classify') {
      return { ok, status, json: async () => document } as Response
    }
    return { ok: true, status: 200, json: async () => verification() } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** One uploaded application, as the classify endpoint reports it. */
function documentOnly(document: ApplicationDocumentResult): ClassificationResult {
  return classification({
    files: [fileClassification('application.pdf', 'application_document')],
    application_document: document,
    label_images: 0,
  })
}

async function attachApplication(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText('Files for this label'), pdfFile())
}

/** The panel the disclosure controls, found the way assistive technology does. */
function panel() {
  const toggle =
    screen.queryByRole('button', { name: TOGGLE }) ?? screen.getByRole('button', { name: REVIEW })
  const id = toggle.getAttribute('aria-controls')
  const found = id ? window.document.getElementById(id) : null
  if (!found) throw new Error('The disclosure names no panel through aria-controls.')
  return found
}

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

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('what greets the agent on the single-label view', () => {
  it('collapses the typed fields by default, so five empty boxes are not the first thing', () => {
    render(<SingleLabelTab />)
    expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'false')
    expect(panel()).not.toBeVisible()
  })

  it('puts the upload before the disclosure, not after it', () => {
    render(<SingleLabelTab />)
    const upload = screen.getByLabelText('Files for this label')
    const toggle = screen.getByRole('button', { name: TOGGLE })
    // Node.DOCUMENT_POSITION_FOLLOWING: the toggle comes after the upload.
    expect(upload.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('no longer frames the upload as the alternative to typing', () => {
    render(<SingleLabelTab />)
    const heading = screen.getByRole('heading', {
      name: /Upload the label application, an image of the label, or both/i,
    })
    // The heading is what says it now. The paragraph under it that explained
    // the one-control idea in four sentences went to Help on 2026-09-01
    // (US-28), under "What do I upload?".
    expect(heading).not.toHaveTextContent(/instead/i)
    expect(screen.queryByText(/One place for everything/i)).not.toBeInTheDocument()
  })

  it('tells the flow in the empty state: upload, then check', () => {
    // Shorter since US-28, and still both verbs: what to do, and where the
    // answer will appear. What each kind of file is for is a Help entry.
    render(<SingleLabelTab />)
    const placeholder = screen.getByText(/Upload a file and select/i)

    expect(placeholder).toBeInTheDocument()
    expect(placeholder).toHaveTextContent(/Check this label/i)
    expect(placeholder).toHaveTextContent(/the results appear here/i)
  })
})

describe('expansion case 1: the agent opens the disclosure', () => {
  it('opens the fields when the agent presses the control, with no document at hand', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.click(screen.getByRole('button', { name: TOGGLE }))

    expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'true')
    expect(panel()).toBeVisible()
    expect(screen.getByLabelText('Brand name')).toBeVisible()
  })

  it('closes them again on a second press, because this is the only case that can close', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    const toggle = screen.getByRole('button', { name: TOGGLE })
    await user.click(toggle)
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(panel()).not.toBeVisible()
  })

  it('is reachable and operable from the keyboard alone', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    const toggle = screen.getByRole('button', { name: TOGGLE })
    toggle.focus()
    expect(toggle).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard(' ')
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
  })

  it('says nothing in the live region, because the control already reports itself', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.click(screen.getByRole('button', { name: TOGGLE }))
    expect(screen.getByLabelText('Application values')).toHaveTextContent('')
  })
})

describe('case 2: a parsed document leaves gaps (US-26)', () => {
  /*
   * Session 10 opened the disclosure here. US-26 goes further: the missing
   * field is shown directly, because that is the same outcome with one fewer
   * moving part, and everything that was read becomes a summary line rather
   * than a box. The behaviour these tests pinned is now pinned in
   * quietFields.test.tsx; what is kept here is that a gap is still loud.
   */
  it('shows the missing values as fields, not behind anything', async () => {
    const user = userEvent.setup()
    stubApi(documentOnly(applicationDocument()))
    render(<SingleLabelTab />)
    await attachApplication(user)

    // The three the form proper has no boxes for at all (A-17).
    await waitFor(() => expect(screen.getByLabelText('Class or type designation')).toBeVisible())
    expect(screen.getByLabelText('Alcohol content')).toBeVisible()
    expect(screen.getByLabelText('Net contents')).toBeVisible()
    expect(screen.getByLabelText('Alcohol content')).toHaveValue('')
  })

  it('summarises what was read rather than putting it back in a box', async () => {
    const user = userEvent.setup()
    stubApi(documentOnly(applicationDocument()))
    render(<SingleLabelTab />)
    await attachApplication(user)

    await waitFor(() => expect(screen.getByText('Read from your upload')).toBeVisible())
    expect(screen.getByText("STONE'S THROW")).toBeVisible()
    // And the box for it is behind the disclosure, still there to correct.
    expect(screen.getByLabelText('Brand name')).not.toBeVisible()
  })

  it('announces which value is missing and what to do about it', async () => {
    const user = userEvent.setup()
    stubApi(documentOnly(applicationDocument()))
    render(<SingleLabelTab />)
    await attachApplication(user)

    const region = screen.getByLabelText('Application values')
    await waitFor(() => expect(region).toHaveTextContent(/not found in your upload/i))
    expect(region).toHaveTextContent(/alcohol content/i)
    expect(region).toHaveTextContent(/net contents/i)
    expect(region).toHaveTextContent(/Enter them, or upload a clearer image/i)
  })

  it('shows no editable field at all when the document carried every value', async () => {
    const user = userEvent.setup()
    stubApi(documentOnly(FULL_DOCUMENT))
    render(<SingleLabelTab />)
    await attachApplication(user)

    // The parse has landed: the values are in the fields.
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))
    // And nothing opened, because there is nothing left for the agent to enter.
    expect(screen.getByRole('button', { name: REVIEW })).toHaveAttribute('aria-expanded', 'false')
    expect(panel()).not.toBeVisible()
    expect(screen.getByLabelText('Application values')).toHaveTextContent('')
  })
})

describe('expansion case 3: the document could not be read (FR-9)', () => {
  /*
   * The classification stands and the file is still listed as the label
   * application; what failed is reading it. So the classify call succeeds and
   * carries the failure in `application_error` (FR-12, ADR 0011).
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

  it('opens the fields as the fallback the error message promises', async () => {
    const user = userEvent.setup()
    stubApi(UNREADABLE)
    render(<SingleLabelTab />)
    await attachApplication(user)

    await screen.findByRole('alert')
    expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByLabelText('Brand name')).toBeVisible()
    expect(screen.getByLabelText('Brand name')).toBeEnabled()
  })

  it('announces that the fields are open, without repeating the error', async () => {
    const user = userEvent.setup()
    stubApi(UNREADABLE)
    render(<SingleLabelTab />)
    await attachApplication(user)

    const region = screen.getByLabelText('Application values')
    await waitFor(() =>
      expect(region).toHaveTextContent(/open below so you can type them in yourself/i),
    )
    // The error itself belongs to the upload's own region, said once.
    expect(region).not.toHaveTextContent(/couldn't read that label application/i)
    expect(screen.getByLabelText('Your uploads')).toHaveTextContent(
      /couldn't read that label application/i,
    )
  })
})

describe('what does not open the fields', () => {
  it('taking a readable document back off the form opens nothing', async () => {
    const user = userEvent.setup()
    stubApi(documentOnly(FULL_DOCUMENT))
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))

    await user.click(screen.getByRole('button', { name: 'Remove application.pdf' }))

    await waitFor(() =>
      expect(screen.queryByText(/Read from the application form/i)).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'false')
  })

  it('uploading a label photograph opens nothing', async () => {
    const user = userEvent.setup()
    stubApi(
      classification({
        files: [fileClassification('label.png')],
        application_document: null,
        label_images: 1,
      }),
    )
    render(<SingleLabelTab />)

    await user.upload(
      screen.getByLabelText('Files for this label'),
      new File([new Uint8Array([137, 80, 78, 71])], 'label.png', { type: 'image/png' }),
    )

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Check this label' })).toBeEnabled(),
    )
    expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'false')
  })
})

describe('beverage type is demoted (A-12, A-13)', () => {
  it('is the last control in the disclosure, not the first field an agent meets', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.click(screen.getByRole('button', { name: TOGGLE }))

    const brand = screen.getByLabelText('Brand name')
    const beverage = screen.getByLabelText('Beverage type')
    expect(brand.compareDocumentPosition(beverage) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('carries no standing caveat on the control itself', async () => {
    /*
     * **Amended by US-28.** The control used to carry two sentences saying that
     * the beverage type is never compared and which numeric rule it selects.
     * Both are true and neither is about the document in front of the agent: it
     * is the same sentence on every check, which is the definition of something
     * that belongs on Help. It is there, under "Where does beverage type come
     * from?", and `helpTab.test.tsx` asserts it.
     *
     * What stays on the control is the sentence that *is* about this document,
     * and it appears only when it applies: item 5's boxes were read and none of
     * them stood out.
     */
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.click(screen.getByRole('button', { name: TOGGLE }))

    expect(screen.getByLabelText('Beverage type')).not.toHaveAccessibleDescription()
    expect(screen.queryByText(/Not compared against the label/i)).not.toBeInTheDocument()
  })

  it('still fills from the document when the document states it', async () => {
    const user = userEvent.setup()
    stubApi(documentOnly(FULL_DOCUMENT))
    render(<SingleLabelTab />)
    await attachApplication(user)

    await waitFor(() =>
      expect(screen.getByLabelText('Beverage type')).toHaveValue('distilled spirits'),
    )
    // It was read, so it is a summary line saying where it came from, and its
    // control is behind the disclosure for an agent who wants to change it.
    expect(screen.getAllByText('Application form').length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: REVIEW }))
    expect(screen.getByLabelText('Beverage type')).toBeVisible()
  })
})
