/**
 * The browser does not launder a value's provenance on its way back out.
 *
 * FR-11, FR-14, ADR 0010, ADR 0013.
 *
 * **The defect these tests exist for.** `artworkDerived.test.tsx` proves the
 * fifth outcome state is counted correctly, and the accessibility suite proves
 * it renders and reads correctly. Both are given a response and asked what the
 * interface does with it. Neither looks at the request, and the defect was in
 * the request: the five boxes are filled from the uploaded document (US-24),
 * and the whole set was then posted back with the check. A value arriving in a
 * typed part is a typed value, so `resolve_application` recorded all five as
 * `typed`, the circularity overlay never fired, and rows that were one reading
 * of one picture compared with itself came back as matches.
 *
 * Measured against the deployed build on 2026-08-30 with the author's own
 * filing: "2 of 5 fields match. 3 does not match." The same document posted to
 * the same endpoint with no application parts at all returns those two rows as
 * `artwork_derived` and the line reads "0 of 3 verifiable fields match; 2 read
 * from the artwork only". The API was right; the round trip through the browser
 * was what broke it.
 *
 * **So these tests assert the request, and against the shape the server really
 * returns.** The classification below is the shape of a document-only
 * submission whose form text carries the brand name and class or type and whose
 * embedded artwork carries the alcohol content and net contents, which is the
 * shape the author's filing produces. The applicant is synthetic: the filing
 * that found this carries a real company, a real tax identifier and a real
 * address, and nothing of it is committed (docs/07_TEST_STRATEGY.md section 8).
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SingleLabelTab } from '../components/SingleLabelTab'
import { typedValues } from '../lib/applicationFields'
import { summary } from '../lib/outcomes'
import {
  applicationDocument,
  classification,
  field,
  fileClassification,
  parsedField,
  phaseTimings,
  photo,
  verification,
  warningDetail,
} from './fixtures'
import { EMPTY_APPLICATION } from '../types'
import type { Outcome, VerificationResult } from '../types'

/**
 * A COLA whose form text answers two fields and whose embedded artwork answers
 * the other two. That split is not incidental: it is what the overlay keys on,
 * and a fixture where everything came from one source could not tell the two
 * halves of the assertion apart.
 */
const DOCUMENT = applicationDocument({
  fields: [
    parsedField('brand_name', "STONE'S THROW", { source: 'embedded_text' }),
    parsedField('class_type', 'KENTUCKY STRAIGHT BOURBON WHISKEY', { source: 'embedded_text' }),
    parsedField('alcohol_content', '45% ALC BY VOL', { source: 'embedded_artwork' }),
    parsedField('net_contents', '750 ML', { source: 'embedded_artwork' }),
    parsedField('beverage_type', null),
  ],
  artwork_images_found: 1,
  artwork_images_read: 1,
  label_artwork_page: 3,
  label_artwork_available: true,
  notes: [],
})

const DOCUMENT_ONLY = classification({
  files: [fileClassification('cola.pdf', 'application_document')],
  application_document: DOCUMENT,
  label_images: 0,
})

/**
 * What POST /api/verify returns for that submission when the browser sends no
 * application parts: the two artwork-derived rows carry the fifth outcome and
 * no score, exactly as `_artwork_derived` builds them.
 */
function artworkDerivedResult(): VerificationResult {
  const base = verification()
  return {
    ...base,
    fields: [
      field('brand_name', 'match', {
        label_value: "STONE'S THROW",
        application_value: "STONE'S THROW",
        application_value_source: 'parsed_from_form',
      }),
      field('class_type', 'match', {
        label_value: 'KENTUCKY STRAIGHT BOURBON WHISKEY',
        application_value: 'KENTUCKY STRAIGHT BOURBON WHISKEY',
        application_value_source: 'parsed_from_form',
      }),
      field('alcohol_content', 'artwork_derived', {
        label_value: '45% ALC BY VOL',
        application_value: '45% ALC BY VOL',
        score: null,
        application_value_source: 'parsed_from_artwork',
      }),
      field('net_contents', 'artwork_derived', {
        label_value: '750 ML',
        application_value: '750 ML',
        score: null,
        application_value_source: 'parsed_from_artwork',
      }),
      field('government_warning', 'match', { application_value_source: 'typed' }),
    ],
    warning_detail: warningDetail(),
    photos: [photo(1, { origin: 'application_artwork' })],
    timings: phaseTimings({ artwork_ocr_ms: 3113.7, label_ocr_ms: 0, tesseract_reads: 4 }),
    application_document: DOCUMENT,
    label_source: 'application_artwork',
    self_consistency_note:
      'Some of this was read from the label artwork inside the application document.',
  }
}

function pdf() {
  return new File([new Uint8Array([37, 80, 68, 70])], 'cola.pdf', { type: 'application/pdf' })
}

/** Stub both endpoints and keep whatever the check posted, for inspection. */
function stubApi(result: VerificationResult = artworkDerivedResult()) {
  const posted: { body: FormData | null } = { body: null }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url === '/api/classify') {
        return { ok: true, status: 200, json: async () => DOCUMENT_ONLY } as Response
      }
      posted.body = (init?.body ?? null) as FormData | null
      return { ok: true, status: 200, json: async () => result } as Response
    }),
  )
  return posted
}

/** The application values in a posted body, as the server would read them. */
function sentValues(body: FormData | null): Record<string, string> {
  const values: Record<string, string> = {}
  body?.forEach((value, key) => {
    if (typeof value === 'string') values[key] = value
  })
  return values
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('what the check posts back', () => {
  it('sends no application value the agent did not type', async () => {
    const posted = stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await user.upload(screen.getByLabelText('Files for this label'), pdf())
    // The boxes are filled from the document, which is US-24 working. What
    // must not follow is those values going back out as the agent's own.
    await waitFor(() => expect(screen.getByDisplayValue("STONE'S THROW")).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() => expect(posted.body).not.toBeNull())
    expect(sentValues(posted.body)).toEqual({
      brand_name: '',
      class_type: '',
      alcohol_content: '',
      net_contents: '',
      beverage_type: '',
    })
  })

  it('sends a value the agent edited, because that one is theirs', async () => {
    const posted = stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await user.upload(screen.getByLabelText('Files for this label'), pdf())
    await waitFor(() => expect(screen.getByDisplayValue("STONE'S THROW")).toBeInTheDocument())

    const box = screen.getByDisplayValue("STONE'S THROW")
    await user.clear(box)
    await user.type(box, 'STONES THROW')
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() => expect(posted.body).not.toBeNull())
    const values = sentValues(posted.body)
    expect(values.brand_name).toBe('STONES THROW')
    // And correcting one field does not claim the other three.
    expect(values.alcohol_content).toBe('')
    expect(values.net_contents).toBe('')
  })

  it('sends what the agent typed when no document was uploaded at all', async () => {
    // The path that has always worked, kept working: with nothing filled in
    // from a document, everything in the boxes is the agent's own.
    const values = typedValues(
      { ...EMPTY_APPLICATION, brand_name: 'GREY HARBOR', net_contents: '750 mL' },
      { brand_name: 'typed', net_contents: 'typed' },
    )

    expect(values.brand_name).toBe('GREY HARBOR')
    expect(values.net_contents).toBe('750 mL')
    expect(values.class_type).toBe('')
  })
})

describe('and what the panel then says about it', () => {
  it('qualifies the count on the response the server really returns', async () => {
    // The assertion the accessibility fixture makes, made here against the
    // response shape this submission actually produces rather than against a
    // hand-written one, and reached through the interface rather than by
    // calling summary() with a list.
    const posted = stubApi()
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await user.upload(screen.getByLabelText('Files for this label'), pdf())
    await waitFor(() => expect(screen.getByDisplayValue("STONE'S THROW")).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Check this label' }))

    await waitFor(() => expect(posted.body).not.toBeNull())
    const line = '3 of 3 verifiable fields match; 2 read from the artwork only'
    expect(await screen.findByText(line)).toBeInTheDocument()
    expect(screen.getByRole('status', { name: 'Check result' })).toHaveTextContent(line)
  })

  it('is the line the laundered response could never produce', () => {
    // The counterfactual, stated once so the regression is legible: the same
    // five rows with the two artwork values posted back as typed come back as
    // matches, and the count says five of five with no qualifier on it.
    const laundered: Outcome[] = ['match', 'match', 'match', 'match', 'match']

    expect(summary(laundered)).toBe('5 of 5 fields match')
    expect(summary(artworkDerivedResult().fields.map((row) => row.outcome))).toBe(
      '3 of 3 verifiable fields match; 2 read from the artwork only',
    )
  })
})
