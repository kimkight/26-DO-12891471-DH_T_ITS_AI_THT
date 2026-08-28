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
import { applicationDocument, parsedField, verification } from './fixtures'

const TOGGLE = /Or type the application values/i

function pdfFile(name = 'application.pdf') {
  return new File([new Uint8Array([37, 80, 68, 70])], name, { type: 'application/pdf' })
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

/** The panel the disclosure controls, found the way assistive technology does. */
function panel() {
  const id = screen.getByRole('button', { name: TOGGLE }).getAttribute('aria-controls')
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

  it('puts the application upload before the disclosure, not after it', () => {
    render(<SingleLabelTab />)
    const upload = screen.getByLabelText('Label application')
    const toggle = screen.getByRole('button', { name: TOGGLE })
    // Node.DOCUMENT_POSITION_FOLLOWING: the toggle comes after the upload.
    expect(upload.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('no longer frames the upload as the alternative to typing', () => {
    render(<SingleLabelTab />)
    const heading = screen.getByRole('heading', { name: /Upload the label application/i })
    expect(heading).not.toHaveTextContent(/instead/i)
    expect(screen.getByText(/This is what the label is checked against/i)).toBeInTheDocument()
  })

  it('tells the flow in the empty state: photos, then the application, then check', () => {
    render(<SingleLabelTab />)
    const placeholder = screen.getByText(/Take your photos, attach the label application/i)
    expect(placeholder).toBeInTheDocument()
    expect(placeholder).toHaveTextContent(/Check this label/i)
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

describe('expansion case 2: a parsed document leaves gaps', () => {
  it('opens the fields when the form did not carry every value', async () => {
    const user = userEvent.setup()
    stubApi(applicationDocument())
    render(<SingleLabelTab />)
    await attachApplication(user)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'true'),
    )
    expect(panel()).toBeVisible()
  })

  it('shows the parsed values filled and the gaps empty', async () => {
    const user = userEvent.setup()
    stubApi(applicationDocument())
    render(<SingleLabelTab />)
    await attachApplication(user)

    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))
    expect(screen.getByLabelText('Brand name')).toBeVisible()
    // The three the form proper has no boxes for at all (A-17).
    expect(screen.getByLabelText('Class or type designation')).toHaveValue('')
    expect(screen.getByLabelText('Alcohol content')).toHaveValue('')
    expect(screen.getByLabelText('Net contents')).toHaveValue('')
  })

  it('announces the expansion and names the gaps that caused it', async () => {
    const user = userEvent.setup()
    stubApi(applicationDocument())
    render(<SingleLabelTab />)
    await attachApplication(user)

    const region = screen.getByLabelText('Application values')
    await waitFor(() => expect(region).toHaveTextContent(/The application values are open below/i))
    expect(region).toHaveTextContent(/class type/i)
    expect(region).toHaveTextContent(/net contents/i)
    expect(region).toHaveTextContent(/What it did carry is already filled in/i)
  })

  it('leaves the fields collapsed when the document carried every value', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)

    // The parse has landed: the values are in the fields.
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))
    // And nothing opened, because there is nothing left for the agent to enter.
    expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'false')
    expect(panel()).not.toBeVisible()
    expect(screen.getByLabelText('Application values')).toHaveTextContent('')
  })
})

describe('expansion case 3: the document could not be read (FR-9)', () => {
  const ERROR_BODY = {
    error: {
      code: 'unreadable_application_document',
      message: 'The uploaded file could not be opened as a PDF.',
      limit: null,
    },
  }

  it('opens the fields as the fallback the error message promises', async () => {
    const user = userEvent.setup()
    stubApi(ERROR_BODY, false, 422)
    render(<SingleLabelTab />)
    await attachApplication(user)

    await screen.findByRole('alert')
    expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByLabelText('Brand name')).toBeVisible()
    expect(screen.getByLabelText('Brand name')).toBeEnabled()
  })

  it('announces that the fields are open, without repeating the error', async () => {
    const user = userEvent.setup()
    stubApi(ERROR_BODY, false, 422)
    render(<SingleLabelTab />)
    await attachApplication(user)

    const region = screen.getByLabelText('Application values')
    await waitFor(() =>
      expect(region).toHaveTextContent(/open below so you can type them in yourself/i),
    )
    // The error itself belongs to the upload's own region, said once.
    expect(region).not.toHaveTextContent(/couldn't read that label application/i)
    expect(screen.getByLabelText('Application form')).toHaveTextContent(
      /couldn't read that label application/i,
    )
  })
})

describe('what does not open the fields', () => {
  it('taking a readable document back off the form opens nothing', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)
    await waitFor(() => expect(screen.getByLabelText('Brand name')).toHaveValue("STONE'S THROW"))

    await user.click(screen.getByRole('button', { name: 'Remove this application form' }))

    await waitFor(() =>
      expect(screen.queryByText(/Read from the application form/i)).not.toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'false')
  })

  it('choosing a label photograph opens nothing', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.upload(
      screen.getByLabelText('Label image'),
      new File([new Uint8Array([137, 80, 78, 71])], 'label.png', { type: 'image/png' }),
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

  it('says it is not compared, and what it does instead', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.click(screen.getByRole('button', { name: TOGGLE }))

    expect(screen.getByLabelText('Beverage type')).toHaveAccessibleDescription(
      /Not compared against the label/i,
    )
    expect(
      screen.getByText(/proof cross-check for spirits, range handling for wine/i),
    ).toBeVisible()
  })

  it('still fills from the document when the document states it', async () => {
    const user = userEvent.setup()
    stubApi(FULL_DOCUMENT)
    render(<SingleLabelTab />)
    await attachApplication(user)

    await waitFor(() =>
      expect(screen.getByLabelText('Beverage type')).toHaveValue('distilled spirits'),
    )
    await user.click(screen.getByRole('button', { name: TOGGLE }))
    expect(screen.getByLabelText('Beverage type')).toHaveAccessibleDescription(
      /Read from the application form/i,
    )
  })
})
