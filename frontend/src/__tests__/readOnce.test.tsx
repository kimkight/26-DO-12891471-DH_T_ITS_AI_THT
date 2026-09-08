/**
 * The prefill pass does not read the artwork, and the interface does not treat
 * what it will read as missing (ADR 0017).
 *
 * `POST /api/classify` now returns the application document's text layer alone
 * and says so in `artwork_read`. On the author's own filing that means the
 * brand name and the class or type arrive at once, and the alcohol content and
 * the net contents do not arrive until the check reads the artwork they are
 * printed on.
 *
 * **The failure this guards against is the interface calling those two a gap.**
 * A gap is the only work left on the screen: the box opens, focus moves into it
 * and a live region says the value was not found in the upload. Saying that
 * about a value the next click reads off the artwork would be the tool asking
 * an agent to do work it is one second from doing itself, and the agent would
 * reasonably do it.
 *
 * The applicant is synthetic (docs/07_TEST_STRATEGY.md section 8).
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SingleLabelTab } from '../components/SingleLabelTab'
import { pendingFromArtwork, pendingFromDocument } from '../lib/pendingArtwork'
import { applicationDocument, classification, fileClassification, parsedField } from './fixtures'

/**
 * The prefill reading of a filing that carries its own artwork: the text layer
 * answered the two items the form has boxes for, the pictures were counted and
 * not read, and nothing is attributed to them.
 */
const PREFILL = applicationDocument({
  fields: [
    parsedField('brand_name', "STONE'S THROW", { source: 'embedded_text' }),
    parsedField('class_type', 'KENTUCKY STRAIGHT BOURBON WHISKEY', { source: 'embedded_text' }),
    parsedField('alcohol_content', null),
    parsedField('net_contents', null),
    parsedField('beverage_type', null),
  ],
  artwork_images_found: 1,
  artwork_images_read: 0,
  artwork_read: false,
  label_artwork_page: null,
  label_artwork_available: false,
  notes: [],
})

const DOCUMENT_ONLY = classification({
  files: [fileClassification('cola.pdf', 'application_document')],
  application_document: PREFILL,
  label_images: 0,
})

/**
 * The prefill reading of a scan: no text layer, so nothing was read at all
 * (ADR 0024). Every value is on its way from the check, and none is a gap.
 */
const SCAN_PREFILL = applicationDocument({
  extraction_path: 'not_read',
  pages_read: 0,
  pages_not_reached: 3,
  fields: [
    parsedField('brand_name', null),
    parsedField('class_type', null),
    parsedField('alcohol_content', null),
    parsedField('net_contents', null),
    parsedField('beverage_type', null),
  ],
  artwork_images_found: 0,
  artwork_images_read: 0,
  artwork_read: false,
  label_artwork_page: null,
  label_artwork_available: false,
  notes: [
    'This file has no text to read, so its pages will be read as pictures when the label is checked.',
  ],
})

const SCAN_ONLY = classification({
  files: [fileClassification('scan.pdf', 'application_document')],
  application_document: SCAN_PREFILL,
  label_images: 0,
})

function pdf() {
  return new File([new Uint8Array([37, 80, 68, 70])], 'cola.pdf', { type: 'application/pdf' })
}

function stubClassify(body = DOCUMENT_ONLY) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => {
      if (url === '/api/classify') {
        return { ok: true, status: 200, json: async () => body } as Response
      }
      throw new Error(`unexpected request to ${url}`)
    }),
  )
}

async function upload() {
  render(<SingleLabelTab />)
  await userEvent.upload(screen.getByLabelText('Files for this label'), pdf())
  await waitFor(() => expect(screen.getByText(/values were filled in/)).toBeInTheDocument())
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('which fields the artwork still owes', () => {
  it('names the values the text layer did not carry', () => {
    expect(pendingFromArtwork(PREFILL)).toEqual(['alcohol_content', 'net_contents'])
  })

  it('names none when the artwork was read', () => {
    expect(
      pendingFromArtwork(applicationDocument({ artwork_read: true, artwork_images_found: 1 })),
    ).toEqual([])
  })

  it('names none on a reading from a server that predates the decision', () => {
    // `artwork_read` absent means the artwork was read, which is what every
    // build before ADR 0017 did.
    expect(pendingFromArtwork(applicationDocument({ artwork_images_found: 1 }))).toEqual([])
  })

  it('names none when the document carried no pictures at all', () => {
    // The case that must stay a real gap: nothing is coming, so the agent types
    // it or the check reports it as not supplied.
    expect(
      pendingFromArtwork(applicationDocument({ artwork_read: false, artwork_images_found: 0 })),
    ).toEqual([])
  })
})

describe('which fields a scan still owes (ADR 0024)', () => {
  it('names every value on a document whose pages were not read', () => {
    // Nothing was read, so nothing is absent yet: all five are on their way.
    expect(pendingFromDocument(SCAN_PREFILL)).toEqual([
      'brand_name',
      'class_type',
      'alcohol_content',
      'net_contents',
      'beverage_type',
    ])
  })

  it('falls back to the artwork rule on a document that was read', () => {
    expect(pendingFromDocument(PREFILL)).toEqual(['alcohol_content', 'net_contents'])
    expect(pendingFromDocument(null)).toEqual([])
  })
})

describe('the screen after a prefill that left the pages unread', () => {
  it('says the file will be read when the label is checked, and asks for nothing', async () => {
    stubClassify(SCAN_ONLY)
    await upload()

    expect(screen.getByText(/values were filled in/).textContent).toContain('has no text to read')
    expect(screen.queryByText(/you will need to enter/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/values were not read/i)).not.toBeInTheDocument()
    expect(document.activeElement).not.toBe(screen.getByLabelText('Brand name'))
  })
})

describe('the screen after a prefill that left the artwork unread', () => {
  it('does not ask the agent to enter what the artwork will supply', async () => {
    stubClassify()
    await upload()

    // The beverage type is still asked for, and rightly: item 5 is three check
    // boxes and no artwork answers it (ADR 0016). The two the artwork will
    // answer are not in the list.
    const asked = screen.getByText(/you will need to enter/i).textContent ?? ''
    expect(asked).toContain('beverage type')
    expect(asked).not.toContain('alcohol content')
    expect(asked).not.toContain('net contents')
  })

  it('opens no inline box and takes no focus for those values', async () => {
    stubClassify()
    await upload()

    // The gaps section is where a box opens and focus lands. It is not here,
    // because nothing was not read: two values are on their way.
    expect(screen.queryByText(/values were not read/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/One value was not read/i)).not.toBeInTheDocument()
    expect(document.activeElement).not.toBe(screen.getByLabelText('Alcohol content'))
  })

  it('summarises neither of them as read', async () => {
    stubClassify()
    await upload()

    const summary = screen.getByRole('heading', { name: 'Read from your upload' }).parentElement
    expect(summary?.textContent).toContain('Brand name')
    expect(summary?.textContent).not.toContain('Alcohol content')
    expect(summary?.textContent).not.toContain('Net contents')
  })

  it('keeps them editable behind the disclosure, so a typed value still wins', async () => {
    stubClassify()
    await upload()

    // Present in the DOM and inside the collapsed panel: FR-11's precedence
    // says a typed value beats a parsed one, and an agent who wants to type one
    // before the check runs may.
    const box = screen.getByLabelText('Alcohol content')
    expect(box.closest('.disclosure__panel')).not.toBeNull()
  })

  it('still shows what the text layer did answer', async () => {
    stubClassify()
    await upload()

    expect(screen.getByText("STONE'S THROW")).toBeInTheDocument()
  })

  it('still asks for a value nothing is going to supply', async () => {
    // A filing with no pictures in it: the two values are genuinely absent, so
    // the interface behaves exactly as it did before ADR 0017.
    stubClassify(
      classification({
        files: [fileClassification('cola.pdf', 'application_document')],
        application_document: applicationDocument({
          fields: PREFILL.fields,
          artwork_read: false,
          artwork_images_found: 0,
          notes: [],
        }),
        label_images: 0,
      }),
    )
    await upload()

    expect(screen.getByText(/values were not read/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Alcohol content')).toHaveFocus()
  })
})
