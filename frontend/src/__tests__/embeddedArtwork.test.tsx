/**
 * The label artwork inside the application, in the interface (ADR 0010, FR-11).
 *
 * The author uploaded a real COLA document to the deployed v1.0.1 build on
 * 2026-08-29 and two of the five fields reconciled. The alcohol content and the
 * net contents were not missing: they were printed on the label artwork
 * embedded in the same file, which the parser never looked at.
 *
 * Two things the interface now has to do, and they are the two tested here.
 * Say which of the four sources each value came from, because a value
 * recognized off a picture can be misread in a way a value read out of a text
 * layer cannot. And say, once, that a label taken out of an application and
 * checked against that application is a self-consistency check rather than a
 * check of a bottle.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ResultCard } from '../components/ResultCard'
import { SingleLabelTab } from '../components/SingleLabelTab'
import { ARTWORK_LABEL_LINE, sourceChipLabel } from '../lib/applicationSources'
import { photoItemLabel, photoListHeading } from '../lib/photos'
import {
  applicationDocument,
  classification,
  field,
  fileClassification,
  parsedField,
  photo,
  verification,
} from './fixtures'

afterEach(() => {
  vi.unstubAllGlobals()
})

function pdfFile(name = 'application.pdf') {
  return new File([new Uint8Array([37, 80, 68, 70])], name, { type: 'application/pdf' })
}

const ARTWORK_DOCUMENT = applicationDocument({
  fields: [
    parsedField('brand_name', "STONE'S THROW"),
    parsedField('class_type', 'KENTUCKY STRAIGHT BOURBON WHISKEY', {
      source: 'embedded_artwork',
    }),
    parsedField('alcohol_content', '45% ALC/VOL', { source: 'embedded_artwork' }),
    parsedField('net_contents', '750 ML', { source: 'embedded_artwork' }),
    parsedField('beverage_type', null),
  ],
  artwork_images_found: 1,
  artwork_images_read: 1,
  label_artwork_available: true,
  notes: [],
})

describe('the four sources a value can come from', () => {
  it('names each one in the agent’s words', () => {
    expect(sourceChipLabel('typed')).toBe('You typed this')
    expect(sourceChipLabel('parsed_from_form')).toBe('Application form')
    expect(sourceChipLabel('parsed_from_artwork')).toBe('Label artwork in the application')
    expect(sourceChipLabel('absent')).toBe('Not supplied')
  })

  it('says on the card that the application value came off the artwork', () => {
    render(
      <ResultCard
        field={field('alcohol_content', 'match', {
          application_value: '45% ALC/VOL',
          application_value_source: 'parsed_from_artwork',
        })}
      />,
    )

    // The label on the value is the whole of it. A sentence under the row
    // saying the same thing was cut on 2026-08-31; the upload card says it once
    // where the values are first shown.
    expect(
      screen.getByText(/on the application \(label artwork in the application\)/i),
    ).toBeInTheDocument()
    expect(screen.queryByText(/not from its text/i)).not.toBeInTheDocument()
  })

  it('labels a value read out of the document’s text as the form, not the artwork', () => {
    render(
      <ResultCard
        field={field('brand_name', 'match', {
          application_value: "STONE'S THROW",
          application_value_source: 'parsed_from_form',
        })}
      />,
    )

    expect(screen.getByText(/on the application \(application form\)/i)).toBeInTheDocument()
  })
})

/** The classification a lone application carrying its own artwork produces. */
const ARTWORK_CLASSIFICATION = classification({
  files: [fileClassification('application.pdf', 'application_document')],
  application_document: ARTWORK_DOCUMENT,
  label_images: 0,
})

describe('the upload tells the agent what came out of the pictures', () => {
  it('names the artwork values and says no photo is needed', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url === '/api/classify'
          ? ({ ok: true, status: 200, json: async () => ARTWORK_CLASSIFICATION } as Response)
          : ({ ok: true, status: 200, json: async () => verification() } as Response),
      ),
    )
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await user.upload(screen.getByLabelText('Files for this label'), pdfFile())

    await waitFor(() =>
      expect(
        screen.getByText(/were read from the label artwork inside this application/i),
      ).toBeInTheDocument(),
    )
    expect(screen.getByText(/you do not have to add an image/i)).toBeInTheDocument()
    // The bottle caveat is not repeated here. The results panel states it once,
    // where the check it qualifies is being read (2026-08-31).
    expect(screen.queryByText(/photo of a bottle/i)).not.toBeInTheDocument()
  })
})

describe('a result checked against the application’s own artwork', () => {
  it('states the limitation once, above the result', async () => {
    const result = {
      ...verification(),
      label_source: 'application_artwork' as const,
      self_consistency_note: 'The API’s longer statement.',
      photos: [photo(1, { origin: 'application_artwork' })],
      application_document: ARTWORK_DOCUMENT,
    }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) =>
        url === '/api/classify'
          ? ({ ok: true, status: 200, json: async () => ARTWORK_CLASSIFICATION } as Response)
          : ({ ok: true, status: 200, json: async () => result } as Response),
      ),
    )
    const user = userEvent.setup()
    render(<SingleLabelTab />)

    await user.upload(screen.getByLabelText('Files for this label'), pdfFile())
    await waitFor(() => expect(screen.getByText(/you do not have to add an image/i)).toBeVisible())
    await user.click(screen.getByRole('button', { name: /check this label/i }))

    await waitFor(() => expect(screen.getByText(ARTWORK_LABEL_LINE)).toBeInTheDocument())
    // Exactly once. Saying it on every card would be noise (NFR-4).
    expect(screen.getAllByText(ARTWORK_LABEL_LINE)).toHaveLength(1)
  })

  it('does not call the artwork a photo', () => {
    const artwork = [photo(1, { origin: 'application_artwork' })]
    expect(photoListHeading(artwork)).toBe('The label artwork from the application')
    expect(photoItemLabel(artwork[0])).toBe('Label artwork from the application')
    expect(photoListHeading([photo()])).toBe('Your photo')
    expect(photoItemLabel(photo(2))).toBe('Photo 2')
  })
})
