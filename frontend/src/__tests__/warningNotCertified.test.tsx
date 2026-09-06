/**
 * The government warning present and not certified (FR-5, ADR 0022).
 *
 * Measured on a real filing: the warning panel reads well except where the
 * printer's registration marks run through it, so the statement is on the
 * label, it does not match word for word, and every line that differs was
 * read too poorly to say whether the difference is the label's. The interface
 * has to say all three things and pass nothing.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OutcomeBadge } from '../components/OutcomeBadge'
import { ResultCard } from '../components/ResultCard'
import { announcement, presentation, rowOutcome, summary } from '../lib/outcomes'
import type { BatchLine, Outcome } from '../types'
import { batchLine, field, warningDetail } from './fixtures'

function row(outcomes: Outcome[]): BatchLine {
  return batchLine('row.png', 1, 1, outcomes)
}

describe('the chip', () => {
  it('says what was established and what was not, in that order', () => {
    expect(presentation('not_certified').label).toBe('Present, not certified')
  })

  it('is styled as something a person acts on, with its own silhouette', () => {
    expect(presentation('not_certified').tone).toBe('review')
    expect(presentation('not_certified').glyph).not.toBe(presentation('needs_review').glyph)
    render(<OutcomeBadge outcome="not_certified" />)
    expect(screen.getByText('Present, not certified')).toBeInTheDocument()
  })
})

describe('what it counts as', () => {
  it('is never a pass', () => {
    expect(summary(['match', 'match', 'match', 'match', 'not_certified'])).toBe(
      '4 of 5 checks passed',
    )
  })

  it('is said in full to a listener, with the action it asks for', () => {
    expect(announcement(['match', 'match', 'match', 'match', 'not_certified'])).toContain(
      'could not be read cleanly enough to certify word for word; check the label itself',
    )
  })

  it('outranks a review on a batch row and is outranked by a mismatch', () => {
    expect(rowOutcome(row(['needs_review', 'match', 'match', 'match', 'not_certified']))).toBe(
      'not_certified',
    )
    expect(rowOutcome(row(['mismatch', 'match', 'match', 'match', 'not_certified']))).toBe(
      'mismatch',
    )
  })
})

describe('the card', () => {
  it('says the prefix was not read rather than that it failed', () => {
    const warning = warningDetail({
      statement_found: true,
      prefix_legible: false,
      prefix_as_printed: 'OeHEAAT Wi WARNING:',
      prefix_is_capitalized: null,
      body_matches_regulation: false,
      not_certified: true,
      differing_lines: 2,
      illegible_lines: 2,
    })
    render(
      <ResultCard
        field={field('government_warning', 'not_certified', {
          display_name: 'Government warning statement',
        })}
        warning={warning}
      />,
    )
    expect(screen.getByText(/was not read as "GOVERNMENT WARNING:"/)).toBeInTheDocument()
    expect(screen.getByText(/capitalization was not checked/)).toBeInTheDocument()
    expect(screen.queryByText(/not in capital letters/)).not.toBeInTheDocument()
  })
})
