/**
 * What the screen says about a check that was made by searching (ADR 0015).
 *
 * The API no longer extracts a value from the label and compares two strings. It
 * asks whether the declared value appears on the label, and it appends one
 * sentence to every row it answers that way, saying what a hit does and does not
 * establish. A caller with no interface has nowhere else to read that sentence,
 * so the API carries it; this interface has somewhere else, so it says it once
 * above the rows instead of five times inside them.
 *
 * That is the same trade the bold-type note already makes (OOS-4), and these
 * tests pin both halves of it: the line appears exactly once, and the row keeps
 * everything else its reason said, including where on the label the value was
 * found.
 *
 * Requirements: FR-1, FR-3, FR-4, FR-10 (the row shows both values and the
 * evidence), NFR-4 (nothing on the screen that does not earn its place).
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ResultCard } from '../components/ResultCard'
import { PRESENCE_LIMIT, anySearched, reasonWithoutLimit } from '../lib/labelSearch'
import { field, warningDetail } from './fixtures'

/** A row the API decided by searching, in the shape the API returns it. */
const SEARCHED = field('brand_name', 'match', {
  label_value: "STONE'S THROW",
  application_value: "Stone's Throw",
  label_region: { column: 0, block: 1 },
  reason:
    `'Stone's Throw' was found on the label, in column 0, block 1, printed as ` +
    `'STONE'S THROW'. ${PRESENCE_LIMIT}`,
})

describe('the limit of a search hit', () => {
  it('is taken off the row, because the panel says it once', () => {
    render(<ResultCard field={SEARCHED} />)
    expect(screen.queryByText(new RegExp('does not show it appears as the brand'))).toBeNull()
  })

  it('leaves the rest of the reason on the row', () => {
    render(<ResultCard field={SEARCHED} />)
    expect(screen.getByText(/found on the label, in column 0, block 1/)).toBeInTheDocument()
  })

  it('is kept on the row when the server wording has moved on', () => {
    /*
     * The strip is exact rather than fuzzy, in the one direction that matters.
     * A build whose sentence no longer matches keeps the server's sentence in
     * the row rather than losing the disclosure entirely.
     */
    const moved = { ...SEARCHED, reason: 'Found. This shows something else entirely.' }
    render(<ResultCard field={moved} />)
    expect(screen.getByText(/This shows something else entirely/)).toBeInTheDocument()
  })

  it('is detected on a result where any row was searched', () => {
    expect(anySearched([SEARCHED.reason, 'Something else.'])).toBe(true)
  })

  it('is not claimed on a result where no row was searched', () => {
    expect(anySearched(['750 mL on both sides.', 'The statement matches.'])).toBe(false)
  })

  it('strips nothing from a reason that never carried it', () => {
    expect(reasonWithoutLimit('750 mL on both sides.')).toBe('750 mL on both sides.')
  })
})

describe('the row shows the label its own casing', () => {
  /*
   * Dave Morrison's case. The declared value is title case and the label is set
   * in capitals; the search reports what the label printed, so an agent can see
   * that the difference is case without being told that it is.
   */
  it('prints the label value as the label printed it', () => {
    render(<ResultCard field={SEARCHED} />)
    expect(screen.getByText("STONE'S THROW")).toBeInTheDocument()
    expect(screen.getByText("Stone's Throw")).toBeInTheDocument()
  })
})

describe('a value the label does not carry', () => {
  const missing = field('brand_name', 'mismatch', {
    found_on_label: false,
    label_value: null,
    application_value: 'STORMY RIDGE',
    score: 42.1,
    reason:
      `'STORMY RIDGE' was not found on the label. The closest text read anywhere ` +
      `on it is 'STONE'S THROW', in column 0, block 1, scoring 42.1 against a ` +
      `review threshold of 80. It is reported as not found rather than as a guess (FR-1).`,
  })

  it('still reads as not found on the label', () => {
    render(<ResultCard field={missing} />)
    expect(screen.getByText('Not found on the label')).toBeInTheDocument()
  })

  it('shows the closest text the label does carry, so the call can be judged', () => {
    render(<ResultCard field={missing} />)
    expect(screen.getByText(/closest text read anywhere on it/)).toBeInTheDocument()
  })
})

describe('the government warning is not routed through any of this', () => {
  it('keeps its own reason and its own bold-type disclosure (FR-5, OOS-4)', () => {
    const warning = warningDetail()
    const row = field('government_warning', 'match', {
      reason: `The statement matches 27 CFR 16.21 word for word. ${warning.bold_type_note}`,
    })
    render(<ResultCard field={row} warning={warning} />)
    expect(screen.getByText(/matches 27 CFR 16.21 word for word/)).toBeInTheDocument()
    expect(screen.getByText(warning.bold_type_note)).toBeInTheDocument()
  })
})
