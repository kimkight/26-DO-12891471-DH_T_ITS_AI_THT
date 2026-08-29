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
import { verification } from './fixtures'

function pngFile(name = 'label.png') {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
}

function respondWith(body: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
  } as Response)
}

async function submitOneLabel(user: ReturnType<typeof userEvent.setup>) {
  await user.upload(screen.getByLabelText('Label image'), pngFile())
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

  it('announces the outcome counts and the time once results arrive', async () => {
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await submitOneLabel(user)

    await waitFor(() => {
      expect(screen.getByRole('status', { name: 'Check result' })).toHaveTextContent(
        /Checked in .* seconds/,
      )
    })
    expect(screen.getByRole('status', { name: 'Check result' })).toHaveTextContent(
      '5 of 5 fields match',
    )
  })

  it('names what needs attention and stays silent about counts that are zero', () => {
    const spoken = announcement(['match', 'match', 'needs_review', 'mismatch', 'match'], 1.8)
    expect(spoken).toContain('Checked in 1.8 seconds.')
    expect(spoken).toContain('3 of 5 fields match.')
    expect(spoken).toContain('1 needs your review.')
    expect(spoken).toContain('1 does not match.')
    expect(spoken).not.toContain('was not compared')
  })
})

describe('the timing line', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('reports the round trip the agent waited for, not just the server figure', async () => {
    vi.stubGlobal('fetch', respondWith(verification()))
    const user = userEvent.setup()
    render(<SingleLabelTab />)
    await submitOneLabel(user)

    // Scoped to the visible line: the live region carries the same sentence,
    // which is the point of it, so an unscoped query matches both.
    await waitFor(() => {
      expect(
        screen.getByText(/Checked in \d+\.\d seconds\./, { selector: 'p.timing' }),
      ).toBeInTheDocument()
    })
    // The server's own elapsed_ms is shown as the detail, so the two are
    // distinguishable rather than conflated (NFR-1).
    expect(screen.getByText(/540 ms of that was inside the checker/)).toBeInTheDocument()
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
    expect(alert).toHaveTextContent("We couldn't read this label. Try a clearer photo.")
    // The API's own message is kept as the detail rather than discarded.
    expect(alert).toHaveTextContent('Could not decode.')
    expect(screen.queryByText('Match')).not.toBeInTheDocument()
  })

  it('says something an agent can act on when the API cannot be reached at all', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
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
      'Label image',
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
    // Two things now turn it on: a photograph, or an application carrying its
    // own label artwork (ADR 0010). The hint names both, because an agent
    // holding only the COLA document should not be told to go and find a
    // bottle.
    render(<SingleLabelTab />)
    expect(screen.getByRole('button', { name: 'Check this label' })).toBeDisabled()
    expect(
      screen.getByText(
        /Choose a label image, or attach an application that carries the label artwork/i,
      ),
    ).toBeInTheDocument()
  })
})
