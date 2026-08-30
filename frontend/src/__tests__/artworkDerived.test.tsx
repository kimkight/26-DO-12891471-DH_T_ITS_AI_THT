/**
 * The fifth outcome state, and the count that stops overstating itself.
 *
 * FR-14, ADR 0013. When the agent uploads only the application document, the
 * label side of the check is the artwork inside that document, and any value
 * the artwork also supplied to the application side is being compared with
 * itself. Such a row can only agree. A green match chip on it would be
 * structurally incapable of ever saying anything else, which is a false
 * assurance and is how a tool loses a sceptical agent permanently.
 *
 * These tests hold the three conditions the author set on filling those values
 * in: its own outcome state excluded from the match tally, the source stated on
 * the row rather than in a footnote, and presence left as an independent
 * finding.
 */
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OutcomeBadge } from '../components/OutcomeBadge'
import { ResultCard } from '../components/ResultCard'
import { announcement, rowOutcome, summary, tally } from '../lib/outcomes'
import { batchLine, field, warningDetail } from './fixtures'
import type { Outcome } from '../types'

/** The author's own submission: the form is silent, the artwork is not. */
const ARTWORK_ONLY: Outcome[] = [
  'match', // brand name, off the form's text layer
  'artwork_derived', // class or type
  'artwork_derived', // alcohol content
  'artwork_derived', // net contents
  'match', // the warning, checked against 27 CFR 16.21
]

describe('the count says what is true rather than five of five', () => {
  it('counts only the rows that could have disagreed, and names the rest', () => {
    expect(summary(ARTWORK_ONLY)).toBe(
      '2 of 2 verifiable fields match; 3 read from the artwork only',
    )
  })

  it('reads in the shape the author specified for two derived rows', () => {
    const outcomes: Outcome[] = ['match', 'match', 'match', 'artwork_derived', 'artwork_derived']
    expect(summary(outcomes)).toBe('3 of 3 verifiable fields match; 2 read from the artwork only')
  })

  it('says nothing about verifiability when nothing was artwork-derived', () => {
    const outcomes: Outcome[] = ['match', 'match', 'match', 'match', 'match']
    expect(summary(outcomes)).toBe('5 of 5 fields match')
  })

  it('does not fold an artwork-derived row into the matches', () => {
    const counts = tally(ARTWORK_ONLY)
    expect(counts.match).toBe(2)
    expect(counts.artwork_derived).toBe(3)
  })

  it('a failing row still reduces the numerator rather than the denominator', () => {
    const outcomes: Outcome[] = ['mismatch', 'match', 'artwork_derived', 'artwork_derived', 'match']
    expect(summary(outcomes)).toBe('2 of 3 verifiable fields match; 2 read from the artwork only')
  })
})

describe('what a screen reader hears matches what the panel prints', () => {
  it('opens with the same summary and then explains the derived rows', () => {
    const spoken = announcement(ARTWORK_ONLY, 1.4)
    expect(spoken).toContain('2 of 2 verifiable fields match; 3 read from the artwork only')
    expect(spoken).toContain('nothing independent to check it against')
  })

  it('never announces an artwork-derived field as matching', () => {
    expect(announcement(ARTWORK_ONLY, 1.4)).not.toContain('5 of 5')
  })
})

describe('the row says why it is different, on the row', () => {
  const derived = field('alcohol_content', 'artwork_derived', {
    label_value: '45% Alc./Vol. (90 Proof)',
    application_value: '45% Alc./Vol. (90 Proof)',
    score: null,
    application_value_source: 'parsed_from_artwork',
  })

  it('names the source and says it is the same source as the label', () => {
    render(<ResultCard field={derived} warning={warningDetail()} />)
    expect(screen.getByText('Source')).toBeInTheDocument()
    expect(screen.getByText('Label artwork (same source as the label)')).toBeInTheDocument()
  })

  it('says what that means without making the agent look anything up', () => {
    render(<ResultCard field={derived} warning={warningDetail()} />)
    expect(screen.getByText(/one reading of one picture/)).toBeInTheDocument()
  })

  it('carries the word, not the colour alone, and its own silhouette', () => {
    const { container } = render(<OutcomeBadge outcome="artwork_derived" />)
    expect(within(container).getByText('Read from the artwork')).toBeInTheDocument()

    const derivedShape = container.querySelector('svg path')?.getAttribute('d')
    const others = (['match', 'needs_review', 'mismatch', 'not_compared'] as Outcome[]).map(
      (outcome) => {
        const rendered = render(<OutcomeBadge outcome={outcome} />)
        const path = rendered.container.querySelector('svg path')?.getAttribute('d')
        rendered.unmount()
        return path
      },
    )
    expect(derivedShape).toBeTruthy()
    expect(others).not.toContain(derivedShape)
  })

  it('never shows a score, because a string scored against itself is not evidence', () => {
    render(<ResultCard field={derived} warning={warningDetail()} />)
    expect(screen.queryByText('100')).not.toBeInTheDocument()
  })
})

describe('presence stays an independent finding', () => {
  it('a mandatory element missing from the artwork is still reported as a finding', () => {
    const absent = field('net_contents', 'mismatch', {
      found_on_label: false,
      label_value: null,
      application_value: null,
      score: null,
      application_value_source: 'absent',
      reason: 'Net contents was not found on the label. 27 CFR 5.63(b)(2) requires it.',
    })
    render(<ResultCard field={absent} warning={warningDetail()} />)

    expect(screen.getByText('Does not match')).toBeInTheDocument()
    expect(screen.queryByText('Read from the artwork')).not.toBeInTheDocument()
    expect(screen.getByText(/27 CFR 5.63\(b\)\(2\)/)).toBeInTheDocument()
  })
})

describe('a batch row is never reported as better than its worst field', () => {
  it('a row carrying an artwork-derived field is not a fully matching row', () => {
    const line = batchLine('0001.png', 1, 1, ARTWORK_ONLY)
    expect(rowOutcome(line)).toBe('artwork_derived')
  })

  it('a real failure still outranks it', () => {
    const line = batchLine('0002.png', 1, 1, [
      'mismatch',
      'artwork_derived',
      'match',
      'match',
      'match',
    ])
    expect(rowOutcome(line)).toBe('mismatch')
  })
})
