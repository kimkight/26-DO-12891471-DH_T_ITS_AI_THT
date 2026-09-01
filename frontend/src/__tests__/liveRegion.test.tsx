/**
 * The live region and the timing line.
 *
 * Requirements: NFR-5's last criterion ("results appearing after submission are
 * announced to assistive technology"), NFR-1 (elapsed time is reported to the
 * agent), FR-9 (an error renders in plain language and reports no match).
 * Stories: US-12, US-13, US-7.
 *
 * `fetch` is stubbed rather than a server started: what is under test is what
 * the interface does with a response, and a real request would make these
 * tests about the backend.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SingleLabelTab } from '../components/SingleLabelTab'
import { announcement } from '../lib/outcomes'
import { classification, verification } from './fixtures'

function pngFile(name = 'label.png') {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
}

/**
 * One stub for both endpoints the view calls (FR-12): `/api/classify` sorts the
 * uploaded files, `/api/verify` runs the check. Only the second is what these
 * tests are about, so the first always answers "one label picture".
 */
function respondWith(body: unknown, ok = true, status = 200) {
  return vi.fn(async (url: string) =>
    url === '/api/classify'
      ? ({
          ok: true,
          status: 200,
          json: async () =>
            classification({ application_document: null, files: [], label_images: 1 }),
        } as Response)
      : ({ ok, status, json: async () => body } as Response),
  )
}

async function submitOneLabel(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText('Files for this label'), pngFile())
  await waitFor(() =>
    expect(screen.getByRole('button', { name: 'Check this label' })).toBeEnabled(),
  )
  await user.click(screen.getByRole('button', { name: 'Check this label' }))
}

describe('the live region', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', respondWith(verification()))
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('is in the DOM before any result exists, so its update is announced', () => {
    render(<SingleLabelTab />)
    // Named, because the photo list has its own status region since ADR 0007
    // and writing both messages into one would have each clobber the other.
    const region = screen.getByRole('status', { name: 'Check result' })
    expect(region).toBeInTheDocument()
    expect(region).toHaveAttribute('aria-live', 'polite')
    expect(region).toHaveTextContent('')
  })

  it('announces the outcome counts once results arrive', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await submitOneLabel(user)

    await waitFor(() => {
      expect(screen.getByRole('status', { name: 'Check result' })).toHaveTextContent(
        '5 of 5 fields match',
      )
    })
  })

  it('names what needs attention and stays silent about counts that are zero', () => {
    const spoken = announcement(['match', 'match', 'needs_review', 'mismatch', 'match'])
    expect(spoken).toContain('3 of 5 fields match.')
    expect(spoken).toContain('1 needs your review.')
    expect(spoken).toContain('1 does not match.')
    expect(spoken).not.toContain('was not compared')
  })
})

describe('the timing is off the screen (2026-08-31)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  /*
   * The author, on the released build: "I don't need the time listed on the
   * screen think about what a regular application looks like do not put all
   * these extra words on the screen that should not be there."
   *
   * The phases are still measured and still in the API response, where the
   * deployment runbook's step 8.3a reads them. What has gone is the tool talking
   * about itself in the middle of somebody's work (NFR-4). These two assert that
   * it has gone from both places it was said, the line and the announcement, so
   * a screen reader is not told a number nobody can see.
   */
  it('shows no elapsed time on the panel', async () => {
    vi.stubGlobal('fetch', respondWith(verification()))
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await submitOneLabel(user)

    await waitFor(() => expect(screen.getByText('5 of 5 fields match')).toBeVisible())
    expect(document.querySelector('p.timing')).toBeNull()
    expect(screen.queryByText(/Checked in/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Where the time went/)).not.toBeInTheDocument()
    expect(screen.queryByText(/inside the checker/)).not.toBeInTheDocument()
  })

  it('announces no elapsed time either', () => {
    expect(announcement(['match', 'match'])).not.toMatch(/second/)
  })
})

describe('an error', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders in plain language, interrupts, and reports no field outcomes (FR-9)', async () => {
    vi.stubGlobal(
      'fetch',
      respondWith(
        { error: { code: 'unreadable_image', message: 'Could not decode.', limit: null } },
        false,
        422,
      ),
    )
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await submitOneLabel(user)

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("We couldn't read this label. Try a clearer image.")
    // The API's own message is kept as the detail rather than discarded.
    expect(alert).toHaveTextContent('Could not decode.')
    expect(screen.queryByText('Match')).not.toBeInTheDocument()
  })

  it('says something an agent can act on when the API cannot be reached at all', async () => {
    // Only the check is unreachable. Sorting the upload succeeded, which is
    // what put the agent in a position to press the button in the first place.
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url === '/api/classify') {
          return {
            ok: true,
            status: 200,
            json: async () =>
              classification({ application_document: null, files: [], label_images: 1 }),
          } as Response
        }
        throw new TypeError('Failed to fetch')
      }),
    )
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await submitOneLabel(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn't reach the label checker/)
  })
})

describe('the form', () => {
  it('binds a label to every input, and does not require any of them (FR-2, NFR-5)', () => {
    render(<SingleLabelTab />)
    for (const label of [
      'Files for this label',
      'Beverage type',
      'Brand name',
      'Class or type designation',
      'Alcohol content',
      'Net contents',
    ]) {
      const control = screen.getByLabelText(label)
      expect(control).toBeInTheDocument()
      // FR-2: a field the application did not supply reads as not compared, so
      // an empty field is a legitimate submission.
      expect(control).not.toBeRequired()
    }
  })

  it('keeps the check off until there is something to check, and says why', () => {
    // Anything uploaded turns it on (FR-12). What cannot be checked is the
    // server's judgement, made on files it has read, and comes back as an FR-9
    // message naming the missing piece; guessing at it here would mean the
    // interface classifying files it has not read.
    render(<SingleLabelTab />)
    expect(screen.getByRole('button', { name: 'Check this label' })).toBeDisabled()
    expect(
      screen.getByText(
        /Upload something to turn on the check: the label application, an image of the label, or both/i,
      ),
    ).toBeInTheDocument()
  })
})
