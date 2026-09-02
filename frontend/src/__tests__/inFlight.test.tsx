/**
 * Answers that arrive after the screen stopped asking (v1.3.0; code review
 * findings 17 and 18; #116, #117).
 *
 * Reset used to leave a single-label check running, so its five cards and its
 * announcement landed on a form the agent had just cleared, under the files
 * for the next label. And a file removed while its classification was in
 * flight was still announced and its values filled in, because the last
 * response to resolve won. Both are the same defect: nothing tied a response
 * to the screen that asked for it.
 *
 * The fetch is stubbed with promises the test resolves by hand, so the late
 * arrival is the test's to time rather than the network's.
 *
 * Requirements: NFR-4, NFR-5 (the announcement says what is on the screen),
 * US-29.
 */
import { act, render, screen, waitFor } from '@testing-library/react'
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

const RESET = 'Clear and start another label'

function pdfFile(name = 'cola.pdf') {
  return new File([new Uint8Array([37, 80, 68, 70])], name, { type: 'application/pdf' })
}

function pngFile(name = 'label.png') {
  return new File([new Uint8Array([137, 80, 78, 71])], name, { type: 'image/png' })
}

const DOCUMENT = applicationDocument({
  fields: [
    parsedField('brand_name', 'SIERRA VERDE'),
    parsedField('class_type', 'MEZCAL'),
    parsedField('alcohol_content', '42% ALC BY VOL'),
    parsedField('net_contents', '750 ML'),
    parsedField('beverage_type', 'distilled spirits'),
  ],
  notes: [],
})

const CLASSIFIED = classification({
  files: [fileClassification('cola.pdf', 'application_document')],
  application_document: DOCUMENT,
  label_images: 0,
})

/** A response the test releases when it chooses, that honours its abort signal. */
function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

function ok(body: unknown) {
  return { ok: true, status: 200, json: async () => body } as Response
}

function abortError() {
  return new DOMException('The operation was aborted.', 'AbortError')
}

afterEach(() => vi.unstubAllGlobals())

describe('reset cancels a check in flight (finding 17)', () => {
  function stubWithSlowCheck() {
    const check = deferred<Response>()
    const signals: AbortSignal[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string, init?: RequestInit) => {
        if (url === '/api/classify') return ok(CLASSIFIED)
        const signal = init?.signal as AbortSignal
        signals.push(signal)
        signal.addEventListener('abort', () => check.reject(abortError()))
        return check.promise
      }),
    )
    return { check, signals }
  }

  it('aborts the request, so a real fetch rejects, and nothing repopulates the screen', async () => {
    const user = userEvent.setup()
    const { signals } = stubWithSlowCheck()
    render(<SingleLabelTab />)
    await user.upload(screen.getByLabelText('Files for this label'), pdfFile())
    await waitFor(() => expect(screen.getByText('Read from your upload')).toBeVisible())
    await user.click(screen.getByRole('button', { name: 'Check this label' }))
    await waitFor(() => expect(signals).toHaveLength(1))
    expect(screen.getByRole('status', { name: 'Check result' })).toHaveTextContent(
      'Checking this label.',
    )

    await user.click(screen.getByRole('button', { name: RESET }))

    expect(signals[0].aborted).toBe(true)
    await waitFor(() =>
      expect(screen.getByRole('status', { name: 'Check result' })).toHaveTextContent(
        'The form was cleared. Upload the next label.',
      ),
    )
    expect(screen.queryByText(/checks passed/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Check this label' })).toBeDisabled()
  })

  it('ignores an answer that arrives anyway after the reset', async () => {
    const user = userEvent.setup()
    const check = deferred<Response>()
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => (url === '/api/classify' ? ok(CLASSIFIED) : check.promise)),
    )
    render(<SingleLabelTab />)
    await user.upload(screen.getByLabelText('Files for this label'), pdfFile())
    await waitFor(() => expect(screen.getByText('Read from your upload')).toBeVisible())
    await user.click(screen.getByRole('button', { name: 'Check this label' }))
    await user.click(screen.getByRole('button', { name: RESET }))
    await user.upload(screen.getByLabelText('Files for this label'), pdfFile('next.pdf'))
    await waitFor(() => expect(screen.getByText('Read from your upload')).toBeVisible())

    // A's answer lands under B's files.
    await act(async () => {
      check.resolve(ok(verification()))
      await Promise.resolve()
    })

    expect(screen.queryByText(/checks passed/)).not.toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Check result' })).not.toHaveTextContent(
      /checks passed/,
    )
    expect(screen.getByText('next.pdf')).toBeInTheDocument()
  })
})

describe('a file removed before its classification returns (finding 18)', () => {
  it('ignores the stale answer: nothing is announced and nothing is filled in', async () => {
    const user = userEvent.setup()
    const first = deferred<Response>()
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => first.promise),
    )
    render(<SingleLabelTab />)
    await user.upload(screen.getByLabelText('Files for this label'), pdfFile())
    expect(screen.getByText('Reading...')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove cola.pdf' }))
    await act(async () => {
      first.resolve(ok(CLASSIFIED))
      await Promise.resolve()
    })

    expect(screen.getByLabelText('Your uploads')).toHaveTextContent('')
    expect(screen.queryByText(/read as a label application/)).not.toBeInTheDocument()
    expect(screen.getByLabelText('Brand name')).toHaveValue('')
    expect(screen.queryByText('Read from your upload')).not.toBeInTheDocument()
    expect(screen.queryByText(/Reading what you uploaded/)).not.toBeInTheDocument()
  })

  it('uses the answer for the list the agent actually has, not the first to resolve', async () => {
    const user = userEvent.setup()
    const first = deferred<Response>()
    const second = deferred<Response>()
    const calls: FormData[] = []
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init?: RequestInit) => {
        calls.push(init?.body as FormData)
        return calls.length === 1 ? first.promise : second.promise
      }),
    )
    render(<SingleLabelTab />)
    await user.upload(screen.getByLabelText('Files for this label'), pdfFile())
    await user.upload(screen.getByLabelText('Files for this label'), pngFile())
    await waitFor(() => expect(calls).toHaveLength(2))

    // The stale answer describes one file; the current list has two.
    await act(async () => {
      first.resolve(ok(CLASSIFIED))
      await Promise.resolve()
    })
    expect(screen.queryByText('Read from your upload')).not.toBeInTheDocument()

    const both = classification({
      files: [
        fileClassification('cola.pdf', 'application_document'),
        fileClassification('label.png'),
      ],
      application_document: DOCUMENT,
      label_images: 1,
    })
    await act(async () => {
      second.resolve(ok(both))
      await Promise.resolve()
    })
    await waitFor(() => expect(screen.getByText('Read from your upload')).toBeVisible())
    expect(screen.getByLabelText('Your uploads')).toHaveTextContent(
      /label\.png, read as a label image/,
    )
  })
})
