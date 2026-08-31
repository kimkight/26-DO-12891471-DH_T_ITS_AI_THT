/**
 * More than one photograph of one label, in the interface (ADR 0007).
 *
 * Requirements: FR-1 (a field found on any photograph is found), FR-9 (all
 * photographs unreadable reads as its own message), FR-10 (the result says
 * which photograph each value came from), NFR-4 (the control is obvious and the
 * cap is not something to run into), NFR-5 (every control is reachable and
 * labelled, and every change to the photo list is announced). Story: US-22.
 */
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { PhotoNotes } from '../components/PhotoNotes'
import { SingleLabelTab } from '../components/SingleLabelTab'
import { photoNote } from '../lib/photos'
import { classification, field, photo, verification } from './fixtures'

function pngFile(name: string) {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
}

/**
 * One stub for both endpoints the single-label view calls (FR-12).
 *
 * `/api/classify` sorts the uploaded files; `/api/verify` runs the check. The
 * classification is stubbed to say every file is a label picture, which is what
 * these tests are about.
 */
function stubApi(result: unknown = null) {
  const fetchMock = vi.fn(async (url: string) => {
    if (url === '/api/classify') {
      return {
        ok: true,
        status: 200,
        json: async () =>
          classification({ application_document: null, files: [], label_images: 1 }),
      } as Response
    }
    return { ok: true, status: 200, json: async () => result ?? verification() } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

/** The FormData sent to `/api/verify`, so the wire format is asserted. */
function verifyForm(): FormData {
  const calls = (globalThis.fetch as unknown as { mock: { calls: [string, RequestInit][] } }).mock
    .calls
  const call = calls.find(([url]) => url === '/api/verify')
  if (!call) throw new Error('No request was made to /api/verify.')
  return call[1].body as FormData
}

/** Choose files through the one picker, the way an agent does (FR-12). */
async function upload(user: ReturnType<typeof userEvent.setup>, ...files: File[]) {
  await user.upload(screen.getByLabelText('Files for this label'), files)
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Check this label' })).toBeEnabled(),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('more than one picture of one label, through one picker', () => {
  it('starts with nothing chosen and the check off', () => {
    render(<SingleLabelTab />)
    expect(screen.getByLabelText('Files for this label')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Check this label' })).toBeDisabled()
  })

  it('takes several pictures at once and lists each one', async () => {
    stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await upload(user, pngFile('front.png'), pngFile('back.png'))

    expect(screen.getByText('front.png')).toBeInTheDocument()
    expect(screen.getByText('back.png')).toBeInTheDocument()
  })

  it('adds to the list rather than replacing it, so a second choice means "and this too"', async () => {
    stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await upload(user, pngFile('front.png'))
    await upload(user, pngFile('back.png'))

    expect(screen.getByText('front.png')).toBeInTheDocument()
    expect(screen.getByText('back.png')).toBeInTheDocument()
  })

  it('offers a labelled control to take any one of them back off', async () => {
    stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await upload(user, pngFile('front.png'), pngFile('back.png'))

    await user.click(screen.getByRole('button', { name: 'Remove front.png' }))

    await waitFor(() => expect(screen.queryByText('front.png')).not.toBeInTheDocument())
    expect(screen.getByText('back.png')).toBeInTheDocument()
  })

  it('turns the check off again when the last file is removed', async () => {
    stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await upload(user, pngFile('only.png'))

    await user.click(screen.getByRole('button', { name: 'Remove only.png' }))

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Check this label' })).toBeDisabled(),
    )
  })
})

describe('what reaches the API', () => {
  it('sends every file under one repeated part, in the order chosen', async () => {
    stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await upload(user, pngFile('front.png'), pngFile('back.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() => expect(verifyForm()).toBeTruthy())
    const sent = verifyForm().getAll('files') as File[]
    expect(sent.map((file) => file.name)).toEqual(['front.png', 'back.png'])
    // Nothing decides which side a file is on before the server has read it.
    expect(verifyForm().getAll('image')).toHaveLength(0)
    expect(verifyForm().getAll('application_document')).toHaveLength(0)
  })

  it('sends exactly one part for a single picture', async () => {
    stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await upload(user, pngFile('only.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() => expect(verifyForm()).toBeTruthy())
    expect(verifyForm().getAll('files')).toHaveLength(1)
  })

  it('does not send the same file twice when it is chosen twice', async () => {
    stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    // The same file, chosen again: a browser hands back a second File object
    // with the same name, size and modified time, which is what identifies it.
    const chosen = pngFile('only.png')

    await upload(user, chosen)
    await user.upload(screen.getByLabelText('Files for this label'), chosen)
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() => expect(verifyForm()).toBeTruthy())
    expect(verifyForm().getAll('files')).toHaveLength(1)
  })
})

describe('what the result says about the photos', () => {
  const twoPhotos = {
    ...verification(),
    photos: [photo(1), photo(2)],
    fields: [
      field('brand_name', 'match', { display_name: 'Brand name', source_photo: 1 }),
      field('class_type', 'match', { display_name: 'Class or type designation', source_photo: 1 }),
      field('alcohol_content', 'match', { display_name: 'Alcohol content', source_photo: 1 }),
      field('net_contents', 'match', { display_name: 'Net contents', source_photo: 2 }),
      field('government_warning', 'match', {
        display_name: 'Government warning statement',
        source_photo: 2,
      }),
    ],
  }

  it('says which photo each field was read from', async () => {
    stubApi(twoPhotos)
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await upload(user, pngFile('front.png'), pngFile('back.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    const card = await screen.findByRole('article', { name: 'Net contents' })
    expect(within(card).getByText(/read from photo 2/i)).toBeInTheDocument()
  })

  it('says nothing about which photo when there was only one', async () => {
    stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await upload(user, pngFile('only.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    // Waits on the summary line rather than on a timing line, which came off
    // the panel on 2026-08-31.
    await screen.findByText(/fields match/, { selector: 'p.summary-line' })
    expect(screen.queryByText(/read from photo/i)).not.toBeInTheDocument()
  })

  it('lists every photo once more than one was sent', async () => {
    stubApi(twoPhotos)
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await upload(user, pngFile('front.png'), pngFile('back.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    const notes = await screen.findByRole('region', { name: 'Your 2 photos' })
    expect(within(notes).getByText(/Photo 1/)).toBeInTheDocument()
    expect(within(notes).getByText(/Photo 2/)).toBeInTheDocument()
  })
})

describe('the note for one photo', () => {
  it('says nothing at all when nothing was done to it', () => {
    expect(photoNote(photo(1))).toBeNull()
  })

  it('says the photo was turned, and by how much', () => {
    const turned = photo(1, {
      orientation: {
        exif_orientation: null,
        exif_transposed: false,
        rotation_degrees: 90,
        method: 'osd',
        confidence: 13,
        check: null,
      },
    })
    expect(photoNote(turned)).toBe('We turned it 90 degrees to read it.')
  })

  it('says the camera saved it sideways', () => {
    const tagged = photo(1, {
      orientation: {
        exif_orientation: 6,
        exif_transposed: true,
        rotation_degrees: 0,
        method: 'osd',
        confidence: 13,
        check: null,
      },
    })
    expect(photoNote(tagged)).toBe('It was saved sideways by the camera.')
  })

  it('says both when both happened', () => {
    const both = photo(1, {
      orientation: {
        exif_orientation: 6,
        exif_transposed: true,
        rotation_degrees: 180,
        method: 'osd',
        confidence: 13,
        check: null,
      },
    })
    expect(photoNote(both)).toBe(
      'It was saved sideways by the camera, and we turned it 180 degrees to read it.',
    )
  })

  it('says a photo could not be read, in plain language (FR-9)', () => {
    const failed = photo(2, {
      text_found: false,
      error: { code: 'no_text_found', message: 'Nothing was read.', limit: null },
    })
    expect(photoNote(failed)).toContain('We could not read this photo.')
    expect(photoNote(failed)).toContain("We couldn't find any text on this image.")
  })

  it('renders nothing for the ordinary single upright photo', () => {
    const { container } = render(<PhotoNotes photos={[photo(1)]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders for a single photo that was turned, because that is worth saying', () => {
    render(
      <PhotoNotes
        photos={[
          photo(1, {
            orientation: {
              exif_orientation: null,
              exif_transposed: false,
              rotation_degrees: 270,
              method: 'osd',
              confidence: 12,
              check: null,
            },
          }),
        ]}
      />,
    )
    expect(screen.getByText(/turned it 270 degrees/)).toBeInTheDocument()
  })
})

describe('when no photo could be read (FR-9)', () => {
  it('renders the multi-photo message rather than the single-photo one', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url === '/api/classify'
          ? ({
              ok: true,
              status: 200,
              json: async () =>
                classification({ application_document: null, files: [], label_images: 1 }),
            } as Response)
          : ({
              ok: false,
              status: 422,
              json: async () => ({
                error: {
                  code: 'all_photos_unreadable',
                  message: 'All 2 photographs of this label were unreadable.',
                  limit: null,
                },
              }),
            } as Response),
      ),
    )
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await upload(user, pngFile('a.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("We couldn't read any of the photos of this label")
    expect(alert).toHaveTextContent('All 2 photographs of this label were unreadable.')
    expect(screen.queryByText('Match')).not.toBeInTheDocument()
  })
})
