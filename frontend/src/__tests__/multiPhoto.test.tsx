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
import { field, photo, verification } from './fixtures'

function pngFile(name: string) {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
}

function respondWith(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({ ok, status, json: async () => body } as Response)
}

/** The FormData the interface actually sent, so the wire format is asserted. */
function sentForm(): FormData {
  return (globalThis.fetch as unknown as { mock: { calls: [string, RequestInit][] } }).mock
    .calls[0][1].body as FormData
}

async function addPhoto(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Add another photo of this label' }))
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('adding and removing photos of one label', () => {
  it('starts with a single photo slot, which is what most checks are', () => {
    render(<SingleLabelTab />)
    expect(screen.getByLabelText('Label image')).toBeInTheDocument()
    expect(screen.queryByLabelText('Label image, photo 2')).not.toBeInTheDocument()
    expect(screen.getByText('(0 of 3 chosen)')).toBeInTheDocument()
  })

  it('adds a second and a third slot, then stops offering more', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await addPhoto(user)
    expect(screen.getByLabelText('Label image, photo 2')).toBeInTheDocument()

    await addPhoto(user)
    expect(screen.getByLabelText('Label image, photo 3')).toBeInTheDocument()

    // The cap is enforced by not offering the control, so an agent never
    // reaches the API's refusal (NFR-4).
    expect(
      screen.queryByRole('button', { name: 'Add another photo of this label' }),
    ).not.toBeInTheDocument()
    // Twice: once as the visible hint under the slots, once in the live region
    // that announced the third slot being added.
    expect(screen.getAllByText(/That is the most photos you can add for one label/)).toHaveLength(2)
  })

  it('announces each change to the photo list (NFR-5)', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    const region = screen.getByRole('status', { name: 'Photo list' })

    await addPhoto(user)
    expect(region).toHaveTextContent('Photo 2 added. You can add 1 more.')

    await addPhoto(user)
    expect(region).toHaveTextContent(
      'Photo 3 added. That is the most photos you can add for one label.',
    )

    await user.click(screen.getByRole('button', { name: 'Remove photo 3' }))
    expect(region).toHaveTextContent('Photo 3 removed. 2 photos left.')
  })

  it('removes the right slot and leaves focus somewhere usable', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await addPhoto(user)
    await user.upload(screen.getByLabelText('Label image, photo 2'), pngFile('second.png'))
    expect(screen.getByText('second.png')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove photo 2' }))

    expect(screen.queryByLabelText('Label image, photo 2')).not.toBeInTheDocument()
    expect(screen.queryByText('second.png')).not.toBeInTheDocument()
    // Focus would otherwise fall to the document body, which loses a keyboard
    // user's place entirely.
    expect(screen.getByRole('button', { name: 'Add another photo of this label' })).toHaveFocus()
  })

  it('never offers to remove the first slot, so a check always has a photo', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await addPhoto(user)
    expect(screen.queryByRole('button', { name: 'Remove photo 1' })).not.toBeInTheDocument()
  })

  it('counts only the slots that actually hold a photo', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.upload(screen.getByLabelText('Label image'), pngFile('first.png'))
    await addPhoto(user)

    expect(screen.getByText('(1 of 3 chosen)')).toBeInTheDocument()
    // An empty second slot does not turn the check off, because the first
    // slot has a photo and one photo is a complete submission.
    expect(screen.getByRole('button', { name: 'Check this label' })).toBeEnabled()
  })
})

describe('what reaches the API', () => {
  it('sends one image part per photo, under the same field name', async () => {
    vi.stubGlobal('fetch', respondWith(verification()))
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await user.upload(screen.getByLabelText('Label image'), pngFile('front.png'))
    await addPhoto(user)
    await user.upload(screen.getByLabelText('Label image, photo 2'), pngFile('back.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
    const images = sentForm().getAll('image') as File[]
    expect(images.map((file) => file.name)).toEqual(['front.png', 'back.png'])
  })

  it('sends exactly one part for a single photo, as it always did', async () => {
    vi.stubGlobal('fetch', respondWith(verification()))
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await user.upload(screen.getByLabelText('Label image'), pngFile('only.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
    expect(sentForm().getAll('image')).toHaveLength(1)
  })

  it('skips a slot that was added and left empty', async () => {
    vi.stubGlobal('fetch', respondWith(verification()))
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await user.upload(screen.getByLabelText('Label image'), pngFile('only.png'))
    await addPhoto(user)
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled())
    expect(sentForm().getAll('image')).toHaveLength(1)
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
    vi.stubGlobal('fetch', respondWith(twoPhotos))
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.upload(screen.getByLabelText('Label image'), pngFile('front.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    const card = await screen.findByRole('article', { name: 'Net contents' })
    expect(within(card).getByText(/read from photo 2/i)).toBeInTheDocument()
  })

  it('says nothing about which photo when there was only one', async () => {
    vi.stubGlobal('fetch', respondWith(verification()))
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.upload(screen.getByLabelText('Label image'), pngFile('only.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await screen.findByText(/Checked in/, { selector: 'p.timing' })
    expect(screen.queryByText(/read from photo/i)).not.toBeInTheDocument()
  })

  it('lists every photo once more than one was sent', async () => {
    vi.stubGlobal('fetch', respondWith(twoPhotos))
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.upload(screen.getByLabelText('Label image'), pngFile('front.png'))
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
      orientation: { exif_transposed: false, rotation_degrees: 90, method: 'osd', confidence: 13 },
    })
    expect(photoNote(turned)).toBe('We turned it 90 degrees to read it.')
  })

  it('says the camera saved it sideways', () => {
    const tagged = photo(1, {
      orientation: { exif_transposed: true, rotation_degrees: 0, method: 'osd', confidence: 13 },
    })
    expect(photoNote(tagged)).toBe('It was saved sideways by the camera.')
  })

  it('says both when both happened', () => {
    const both = photo(1, {
      orientation: { exif_transposed: true, rotation_degrees: 180, method: 'osd', confidence: 13 },
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
              exif_transposed: false,
              rotation_degrees: 270,
              method: 'osd',
              confidence: 12,
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
      respondWith(
        {
          error: {
            code: 'all_photos_unreadable',
            message: 'All 2 photographs of this label were unreadable.',
            limit: null,
          },
        },
        false,
        422,
      ),
    )
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await user.upload(screen.getByLabelText('Label image'), pngFile('a.png'))
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("We couldn't read any of the photos of this label")
    expect(alert).toHaveTextContent('All 2 photographs of this label were unreadable.')
    expect(screen.queryByText('Match')).not.toBeInTheDocument()
  })
})
