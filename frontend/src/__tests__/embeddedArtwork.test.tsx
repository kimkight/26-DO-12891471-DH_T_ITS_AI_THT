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
import { artworkNote, photoItemLabel, photoListHeading } from '../lib/photos'
import { PhotoNotes } from '../components/PhotoNotes'
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
  it('says nothing standing about the pictures, because both lines went to Help', async () => {
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

    await waitFor(() => expect(screen.getByText(/values were filled in/i)).toBeInTheDocument())

    /*
     * **Amended by US-28.** Two sentences used to appear here: which values came
     * off the pictures, and that the application carries its own artwork so no
     * image is needed. Both are answers to standing questions rather than
     * statements about this document, and both are on the Help tab, under "What
     * do I upload?" and "Why does it sometimes say a value came from the label
     * artwork inside the application?".
     *
     * What tells an agent that a value came off a picture on this screen is the
     * chip beside the value, which says it in four words, and the result row's
     * own source line. Neither is prose.
     */
    expect(
      screen.queryByText(/were read from the label artwork inside this application/i),
    ).not.toBeInTheDocument()
    expect(screen.queryByText(/you do not have to add an image/i)).not.toBeInTheDocument()
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
    await waitFor(() => expect(screen.getByText(/values were filled in/i)).toBeVisible())
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

describe('a filing whose labels are separate panels (ADR 0010 as amended, #121)', () => {
  const panels = [
    photo(1, {
      origin: 'application_artwork',
      artwork_panel: { page: 2, width: 1350, height: 300 },
    }),
    photo(2, {
      origin: 'application_artwork',
      artwork_panel: { page: 3, width: 1050, height: 309 },
    }),
  ]

  it('names each panel by its page and size, so three pieces of artwork are not three of the same line', () => {
    expect(photoListHeading(panels)).toBe('The 2 pieces of label artwork from the application')
    expect(photoItemLabel(panels[0])).toBe(
      'Label artwork on page 2 of the application, 1350 by 300 pixels',
    )
    expect(photoItemLabel(panels[1])).toBe(
      'Label artwork on page 3 of the application, 1050 by 309 pixels',
    )
  })

  it('says what was set aside and why, with the sizes, and what cleared the floor unread', () => {
    const document = applicationDocument({
      artwork_images_found: 3,
      artwork_images_read: 2,
      artwork_images_rejected: [{ page: 5, width: 687, height: 195, reason: 'area' }],
      artwork_images_accepted: [
        { page: 2, width: 1350, height: 300, status: 'read', ocr_confidence: 95.5 },
        { page: 3, width: 1050, height: 309, status: 'read', ocr_confidence: 95.6 },
        { page: 4, width: 187, height: 1697, status: 'not_read', ocr_confidence: null },
      ],
    })
    expect(artworkNote(document)).toBe(
      'One picture in the application was set aside as too small to be label artwork: ' +
        '687 by 195 on page 5. One picture cleared the size floor and was not read as label ' +
        'artwork: 187 by 1697 on page 4 (past the limit on how many pictures are read).',
    )
    // Nothing to say is the ordinary case, and it says nothing.
    expect(artworkNote(applicationDocument())).toBeNull()
    expect(artworkNote(null)).toBeNull()
  })

  it('renders the table under the artwork list, where the agent reads which panel was which', () => {
    const document = applicationDocument({
      artwork_images_rejected: [{ page: 5, width: 687, height: 195, reason: 'area' }],
      artwork_images_accepted: [
        { page: 2, width: 1350, height: 300, status: 'read', ocr_confidence: 95.5 },
      ],
    })
    render(<PhotoNotes photos={panels} document={document} />)
    expect(screen.getByText(/page 2 of the application, 1350 by 300 pixels/)).toBeInTheDocument()
    expect(
      screen.getByText(/set aside as too small to be label artwork: 687 by 195 on page 5/),
    ).toBeInTheDocument()
  })
})
