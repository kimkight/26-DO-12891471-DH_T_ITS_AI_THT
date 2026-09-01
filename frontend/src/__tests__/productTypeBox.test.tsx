/**
 * The beverage type, read from item 5's ticked box (ADR 0016).
 *
 * The API gains a fifth provenance, `read_from_tick`. It is separate from the
 * other four for the reason the artwork source was separated from the text one:
 * a value measured off pixels can be misread in a way a value read out of a text
 * layer cannot, and an agent looking at a prefilled field is entitled to know
 * which of those they are looking at.
 *
 * It is separate from `parsed_from_artwork` too. Both are pictures, and they are
 * different pictures: one is the label the applicant affixed, the other is the
 * form's own page. An agent checking the artwork is not checking item 5.
 *
 * Requirements: FR-11 (parsed values are surfaced for confirmation and stay
 * editable), FR-13, NFR-5. A-17, amended.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ApplicationFields } from '../components/ApplicationFields'
import { documentSource, fieldSourceMark, sourceChipLabel } from '../lib/applicationSources'
import { EMPTY_APPLICATION } from '../types'
import type { ApplicationData } from '../types'

const APPLICATION: ApplicationData = {
  ...EMPTY_APPLICATION,
  brand_name: "STONE'S THROW",
  beverage_type: 'distilled spirits',
}

function renderFields(sources: Record<string, string>) {
  render(
    <ApplicationFields
      application={APPLICATION}
      sources={sources as never}
      processed
      gaps={[]}
      open={false}
      onToggle={() => {}}
      onChange={() => {}}
      onGapNews={() => {}}
    />,
  )
}

describe('a value read from a ticked box says so', () => {
  it('maps the document source onto its own chip', () => {
    expect(documentSource('product_type_box')).toBe('read_from_tick')
  })

  it('has a chip of its own rather than sharing the form one', () => {
    expect(sourceChipLabel('read_from_tick')).toBe('Ticked box on the form')
    expect(sourceChipLabel('read_from_tick')).not.toBe(sourceChipLabel('parsed_from_form'))
  })

  it('is not presented as the label artwork, which is a different picture', () => {
    expect(sourceChipLabel('read_from_tick')).not.toBe(sourceChipLabel('parsed_from_artwork'))
  })

  it('tells the agent they may change it, like every other parsed value', () => {
    const mark = fieldSourceMark('read_from_tick')
    expect(mark).toContain('item 5')
    expect(mark).toContain('Change it if it is wrong')
  })

  it('shows the chip beside the value that was read', () => {
    renderFields({ brand_name: 'parsed_from_form', beverage_type: 'read_from_tick' })
    expect(screen.getByText('Ticked box on the form')).toBeInTheDocument()
    expect(screen.getByText('distilled spirits')).toBeInTheDocument()
  })
})

describe('a document that did not settle item 5', () => {
  it('says the boxes were read and none stood out, and offers the selector', () => {
    render(
      <ApplicationFields
        application={{ ...EMPTY_APPLICATION, brand_name: "STONE'S THROW" }}
        sources={{ brand_name: 'parsed_from_form', beverage_type: 'absent' } as never}
        processed
        gaps={['beverage_type']}
        open={false}
        onToggle={() => {}}
        onChange={() => {}}
        onGapNews={() => {}}
      />,
    )
    expect(screen.getByLabelText('Beverage type')).toHaveAccessibleDescription(
      /item 5’s boxes were read from the page and none of them stood out/i,
    )
  })
})
