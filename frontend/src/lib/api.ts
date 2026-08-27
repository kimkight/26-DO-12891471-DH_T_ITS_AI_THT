/**
 * The three calls this interface makes, and nothing else.
 *
 * All plain `fetch` against the same origin, because the backend serves the
 * built frontend from its own container (docs/05_ARCHITECTURE.md). There is no
 * client library and no state manager: three endpoints do not need one, and
 * NFR-4 is better served by an interface with less machinery under it.
 */
import { NETWORK_MESSAGE, plainMessage } from './plainLanguage'
import type {
  ApplicationData,
  ApplicationDocumentResult,
  BatchLine,
  ErrorDetail,
  VerificationResult,
} from '../types'

/** What the UI shows when something goes wrong: a plain line plus the detail. */
export interface UiError {
  message: string
  detail: string | null
}

export interface SingleOutcome {
  result: VerificationResult | null
  error: UiError | null
  /** Round trip as the agent experienced it, in seconds. */
  seconds: number
}

export interface ApplicationOutcome {
  document: ApplicationDocumentResult | null
  error: UiError | null
}

function toUiError(body: unknown): UiError {
  const error = (body as { error?: ErrorDetail } | null)?.error
  const detail = [error?.message, error?.limit].filter(Boolean).join(' ')
  return { message: plainMessage(error?.code), detail: detail || null }
}

/**
 * Verify one label, from one to three photographs of it (FR-1 through FR-7,
 * ADR 0007).
 *
 * The elapsed time reported to the agent is measured here, around the whole
 * request, not taken from the response. NFR-1 is about what an agent waits
 * for, and the server's own `elapsed_ms` excludes the upload and the response.
 * The server figure is still shown, as the detail underneath.
 */
export async function verifyLabel(
  images: File[],
  application: ApplicationData,
): Promise<SingleOutcome> {
  const body = new FormData()
  // One `image` part per photograph of the same label (ADR 0007). One part is
  // exactly the request this function always sent, so a single-photograph
  // submission is unchanged on the wire.
  for (const image of images) body.append('image', image)
  for (const [key, value] of Object.entries(application)) {
    body.append(key, value)
  }

  const started = performance.now()
  let response: Response
  try {
    response = await fetch('/api/verify', { method: 'POST', body })
  } catch {
    return {
      result: null,
      error: { message: NETWORK_MESSAGE, detail: null },
      seconds: (performance.now() - started) / 1000,
    }
  }
  const seconds = (performance.now() - started) / 1000

  if (!response.ok) {
    return { result: null, error: toUiError(await safeJson(response)), seconds }
  }
  return { result: (await response.json()) as VerificationResult, error: null, seconds }
}

/**
 * Read a COLA document and return what it says, verifying nothing (FR-11).
 *
 * Called when the agent attaches the label application, before any check runs.
 * The values come back so the interface can put them into the same fields the
 * agent would have typed into, marked as read from the application form and
 * still editable: the check then runs on what the agent confirmed, which is
 * what keeps the judgement theirs (FR-3, ADR 0008).
 *
 * This is document parsing, not COLA system integration. The request goes to
 * this application's own origin; nothing here reaches TTB (OOS-1, NFR-3).
 */
export async function readApplication(document: File): Promise<ApplicationOutcome> {
  const body = new FormData()
  body.append('application_document', document)

  let response: Response
  try {
    response = await fetch('/api/read-application', { method: 'POST', body })
  } catch {
    return { document: null, error: { message: NETWORK_MESSAGE, detail: null } }
  }
  if (!response.ok) return { document: null, error: toUiError(await safeJson(response)) }
  return { document: (await response.json()) as ApplicationDocumentResult, error: null }
}

/**
 * Verify a batch, calling `onLine` as each result arrives (FR-8, NFR-2).
 *
 * The response is newline-delimited JSON, so it is read from the body stream
 * rather than awaited whole. That is the entire point of the design in
 * ADR 0006: a caller that waits for the last byte reinstates the frozen page
 * NFR-2 forbids, however the server sends it.
 *
 * A partial line is held back until its newline arrives. Chunk boundaries fall
 * wherever the network puts them, not on record boundaries, and a JSON.parse of
 * half a line would drop a result that did arrive.
 */
export async function verifyBatch(
  images: File[],
  applications: File,
  onLine: (line: BatchLine) => void,
  signal?: AbortSignal,
): Promise<UiError | null> {
  const body = new FormData()
  for (const image of images) body.append('images', image)
  body.append('applications', applications)

  let response: Response
  try {
    response = await fetch('/api/verify-batch', { method: 'POST', body, signal })
  } catch (cause) {
    if ((cause as Error)?.name === 'AbortError') return null
    return { message: NETWORK_MESSAGE, detail: null }
  }

  if (!response.ok) return toUiError(await safeJson(response))
  if (!response.body) return { message: NETWORK_MESSAGE, detail: null }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffered = ''

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffered += decoder.decode(value, { stream: true })
      const parts = buffered.split('\n')
      // The last element is whatever followed the final newline, which is an
      // incomplete record unless it is empty. It stays buffered.
      buffered = parts.pop() ?? ''
      for (const part of parts) {
        if (part.trim()) onLine(JSON.parse(part) as BatchLine)
      }
    }
    if (buffered.trim()) onLine(JSON.parse(buffered) as BatchLine)
  } catch (cause) {
    if ((cause as Error)?.name === 'AbortError') return null
    // Results already delivered through onLine are kept. A stream that stops
    // early has still done most of its work, and discarding it is the failure
    // NFR-2 names.
    return {
      message: 'The batch stopped before it finished. The results below are the ones that arrived.',
      detail: null,
    }
  }
  return null
}

async function safeJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return null
  }
}
