/**
 * A government warning that differs by one or two characters (FR-5, ADR 0012).
 *
 * FR-5's exactness is deliberate and is not loosened here. What the interface
 * has to do is show the difference, so an agent can tell an OCR artifact from a
 * real defect: "does not match word for word" is equally true of one wrong
 * character and of a missing clause, and the difference between those two is
 * the whole of the agent's decision.
 *
 * Requirements: FR-5, FR-6 (the two checks stay separate), FR-3 (the evidence
 * is shown so the call can be judged rather than trusted), NFR-5 (the
 * distinction survives greyscale, so it is carried by text as well as by
 * styling).
 */
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ResultCard } from '../components/ResultCard'
import { field, warningDetail } from './fixtures'

/** The author's own case, 2026-08-29: `MPAIRS` read for `IMPAIRS`. */
const NEAR_MISS = warningDetail({
  body_matches_regulation: false,
  edit_distance: 1,
  near_miss: true,
  diff: [
    { kind: 'same', text: '(2) Consumption of alcoholic beverages ' },
    { kind: 'missing', text: 'i' },
    { kind: 'same', text: 'mpairs your ability to drive a car.' },
  ],
})

const MISMATCH = warningDetail({
  body_matches_regulation: false,
  edit_distance: 24,
  near_miss: false,
  diff: [
    { kind: 'same', text: 'impairs your ability to drive a car' },
    { kind: 'missing', text: ' or operate machinery' },
    { kind: 'same', text: '.' },
  ],
})

function renderWarning(warning = NEAR_MISS, outcome: 'needs_review' | 'mismatch' = 'needs_review') {
  render(
    <ResultCard
      field={field('government_warning', outcome, {
        display_name: 'Government warning statement',
      })}
      warning={warning}
    />,
  )
}

describe('a near miss', () => {
  it('says how many characters differ', () => {
    renderWarning()
    expect(screen.getByText(/Difference from 27 CFR 16.21: 1 character/)).toBeInTheDocument()
  })

  it('says it is not a match and not automatically a problem', () => {
    renderWarning()
    expect(
      screen.getByText(/as likely to be a reading error as a defect on the label/i),
    ).toBeInTheDocument()
    expect(screen.getByText(/It is not a match/i)).toBeInTheDocument()
  })

  it('shows the exact character that differs, as a deletion', () => {
    renderWarning()
    const removed = screen.getByText('i', { selector: 'del' })
    expect(removed).toBeInTheDocument()
    expect(removed.tagName).toBe('DEL')
  })

  it('carries the two kinds of run in text, not only in colour (NFR-5)', () => {
    renderWarning()
    // The screen-reader prefix inside each marked run.
    expect(screen.getByText('missing:', { exact: false, selector: 'span' })).toBeInTheDocument()
    // And a legend under the block, for a sighted reader in greyscale.
    expect(screen.getByText(/Struck-through text is required by 27 CFR 16.21/i)).toBeInTheDocument()
  })

  it('keeps the whole statement readable, so it is a difference and not a summary', () => {
    renderWarning()
    const block = screen.getByText(/Consumption of alcoholic beverages/).closest('p')
    expect(within(block!).getByText(/mpairs your ability to drive a car/)).toBeInTheDocument()
  })

  it('is reported as needing review rather than as a match or a mismatch', () => {
    renderWarning()
    expect(screen.getByText('Needs review')).toBeInTheDocument()
  })
})

describe('a genuine mismatch', () => {
  it('still shows the difference, because it is evidence either way', () => {
    renderWarning(MISMATCH, 'mismatch')
    expect(screen.getByText(/Difference from 27 CFR 16.21$/)).toBeInTheDocument()
    expect(screen.getByText(/or operate machinery/, { selector: 'del' })).toBeInTheDocument()
  })

  it('does not offer the near-miss reassurance', () => {
    renderWarning(MISMATCH, 'mismatch')
    expect(
      screen.queryByText(/as likely to be a reading error as a defect/i),
    ).not.toBeInTheDocument()
  })

  it('does not name a character count it has no use for', () => {
    renderWarning(MISMATCH, 'mismatch')
    expect(screen.queryByText(/24 characters/)).not.toBeInTheDocument()
  })
})

describe('an exact match', () => {
  it('shows no difference block at all', () => {
    render(
      <ResultCard
        field={field('government_warning', 'match', {
          display_name: 'Government warning statement',
        })}
        warning={warningDetail()}
      />,
    )

    expect(screen.queryByText(/Difference from 27 CFR 16.21/)).not.toBeInTheDocument()
    expect(screen.getByText(/Capitalization of the prefix/)).toBeInTheDocument()
  })
})
