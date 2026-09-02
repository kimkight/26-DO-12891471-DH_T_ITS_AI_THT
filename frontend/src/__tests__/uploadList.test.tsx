/**
 * The small ones on the upload list and the error lines (v1.3.0; code review
 * findings 22, 30, 31 and 32).
 *
 * Requirements: FR-9 (every rejection has a plain-language line that names the
 * problem), FR-12 (each file's classification is shown), NFR-4, NFR-5.
 */
import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SingleLabelTab } from '../components/SingleLabelTab'
import { FilePreview } from '../components/Ui'
import { canPreview, previewPlaceholder } from '../lib/preview'
import { MESSAGES, plainMessage } from '../lib/plainLanguage'
import { classification, fileClassification } from './fixtures'

afterEach(() => vi.unstubAllGlobals())

describe('two files with the same name (finding 31)', () => {
  it('gives each its own chip, by position rather than by name', async () => {
    const user = userEvent.setup()
    const sorted = classification({
      files: [
        fileClassification('label.png'),
        fileClassification('label.png', 'application_document'),
      ],
      application_document: null,
      label_images: 1,
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => ({ ok: true, status: 200, json: async () => sorted }) as Response),
    )
    render(<SingleLabelTab />)

    // Same name, different sizes: two files, and the panel keeps both.
    await user.upload(screen.getByLabelText('Files for this label'), [
      new File([new Uint8Array([137, 80, 78, 71])], 'label.png', { type: 'image/png' }),
      new File([new Uint8Array([137, 80, 78, 71, 0, 0])], 'label.png', { type: 'image/png' }),
    ])

    await waitFor(() => expect(screen.getAllByRole('listitem')).toHaveLength(2))
    const [first, second] = screen.getAllByRole('listitem')
    expect(within(first).getByText('Label image')).toBeInTheDocument()
    expect(within(second).getByText('Label application')).toBeInTheDocument()
  })
})

describe('a picture the browser cannot draw (finding 32)', () => {
  it('shows a placeholder naming the type instead of a broken image', async () => {
    const user = userEvent.setup()
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          ({
            ok: true,
            status: 200,
            json: async () =>
              classification({
                files: [fileClassification('label.tif')],
                application_document: null,
                label_images: 1,
              }),
          }) as Response,
      ),
    )
    render(<SingleLabelTab />)

    await user.upload(
      screen.getByLabelText('Files for this label'),
      new File([new Uint8Array([73, 73, 42, 0])], 'label.tif', { type: 'image/tiff' }),
    )

    const placeholder = await screen.findByTestId('preview-placeholder')
    expect(placeholder).toHaveTextContent(/TIFF image/)
    expect(screen.queryByAltText('Preview of label.tif')).not.toBeInTheDocument()
    // The frame still names the file, once.
    expect(screen.getByText('label.tif')).toBeInTheDocument()
  })

  it('decides by type: JPEG, PNG and WebP preview, TIFF does not', () => {
    // jsdom has no object URLs, so the browser capability is stubbed in.
    vi.stubGlobal('URL', {
      ...URL,
      createObjectURL: () => 'blob:stub',
      revokeObjectURL: () => undefined,
    })
    const of = (type: string) => new File([new Uint8Array([1])], 'x', { type })

    expect(canPreview(of('image/png'))).toBe(true)
    expect(canPreview(of('image/jpeg'))).toBe(true)
    expect(canPreview(of('image/webp'))).toBe(true)
    expect(canPreview(of('image/tiff'))).toBe(false)
    expect(previewPlaceholder(of('image/tiff'))).toMatch(/TIFF image/)
  })

  it('renders the placeholder in the frame, never an img, for a TIFF', () => {
    render(
      <FilePreview file={new File([new Uint8Array([1])], 'scan.tiff', { type: 'image/tiff' })} />,
    )
    expect(screen.getByTestId('preview-placeholder')).toHaveTextContent(/TIFF/)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})

describe('file_too_large says what was too large (finding 30)', () => {
  it('reads the server message to tell one file from a whole submission', () => {
    expect(
      plainMessage(
        'file_too_large',
        'The uploaded file is larger than this service accepts. Send a smaller image.',
      ),
    ).toBe('That file is too large. Send a smaller one.')
    expect(
      plainMessage(
        'file_too_large',
        'This submission is larger than this service accepts in one request. Send fewer photographs of the label, or smaller ones.',
      ),
    ).toMatch(/too large to send together/)
    expect(
      plainMessage(
        'file_too_large',
        'This submission is larger than this service accepts in one request. Split it into smaller batches and send them one after another.',
      ),
    ).toMatch(/Split it into smaller batches/)
  })

  it('no longer calls every oversize file an image', () => {
    expect(plainMessage('file_too_large')).not.toMatch(/image/)
    expect(MESSAGES.file_too_large).not.toMatch(/image/)
  })
})

/*
 * Every error code the server can send has a line (finding 22). The list is
 * read off the backend's own source rather than typed here, so a code added
 * to `backend/app` without a line fails this test rather than reaching an
 * agent as the generic fallback.
 */
describe('every server error code has a plain-language line (finding 22)', () => {
  const backend = resolve(process.cwd(), '..', 'backend', 'app')
  const codes = new Set<string>()
  for (const name of readdirSync(backend)) {
    if (!name.endsWith('.py')) continue
    const source = readFileSync(resolve(backend, name), 'utf-8')
    for (const match of source.matchAll(/(?:code=|_error\(\d+,\s*)"([a-z_]+)"/g)) {
      codes.add(match[1])
    }
  }
  const FALLBACK = plainMessage('a-code-that-does-not-exist')

  it('found the codes in the backend source', () => {
    expect(codes.size).toBeGreaterThanOrEqual(15)
    expect(codes.has('no_label_to_check')).toBe(true)
    expect(codes.has('too_many_application_documents')).toBe(true)
    expect(codes.has('no_files')).toBe(true)
  })

  it.each([...codes].sort())('%s reads as something other than the fallback', (code) => {
    expect(plainMessage(code)).not.toBe(FALLBACK)
  })
})
