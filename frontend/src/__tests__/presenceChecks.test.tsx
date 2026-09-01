/**
 * Contains: a presence check, styled like a pass, with one side (FR-15,
 * ADR 0018).
 *
 * The author, on the released build: "Alcohol content and net content needs to
 * also say 'match' or 'Contains' in green when these items are found on the
 * artwork (that is the requirement right? to have the volume and alcohol
 * content listed?)."
 *
 * It is the requirement, and the row used to throw the finding away. 27 CFR
 * requires alcohol content and net contents on the label; when the artwork
 * carries them, the tool has established something real and positive about the
 * label, whatever the application form says.
 *
 * The circular part was never that finding. It was comparing a value read off
 * the artwork against the same picture, and printing the identical string in
 * both columns, which is what invited an agent to read a comparison into a row
 * that never made one. So the row has no application side, and its chip says
 * "Contains" rather than "Match": one thing was found, and two things did not
 * agree.
 *
 * The applicant is synthetic (docs/07_TEST_STRATEGY.md section 8).
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OutcomeBadge } from '../components/OutcomeBadge'
import { ResultCard } from '../components/ResultCard'
import { announcement, presentation, rowOutcome, summary } from '../lib/outcomes'
import { batchLine, field, warningDetail } from './fixtures'
import type { BatchLine, Outcome } from '../types'

/** The row the API returns for a presence check: one side, no score. */
function presenceRow(name = 'alcohol_content') {
  return field(name, 'present', {
    label_value: '42% ALC BY VOL',
    application_value: null,
    application_value_source: 'absent',
    score: null,
    reason:
      'Alcohol content is on the label: 42% ALC BY VOL. 27 CFR 5.63(a)(3) requires it on a ' +
      'distilled spirits label and 27 CFR 4.32(b)(3) on a wine label, and the label carries ' +
      'it. The application declared no value, so this is a check that the required element is ' +
      'present rather than a comparison of two values.',
  })
}

describe('the chip', () => {
  it('reads Contains, not Match', () => {
    expect(presentation('present').label).toBe('Contains')
  })

  it('is styled like a pass, in the same green as Match', () => {
    expect(presentation('present').tone).toBe(presentation('match').tone)
  })

  it('carries its own silhouette, because it cannot rely on the colour', () => {
    // Match and Contains share a tone by design, so the shape is what separates
    // them under a greyscale check (NFR-5, Section 508 via WCAG 2.0 AA 1.4.1).
    expect(presentation('present').glyph).not.toBe(presentation('match').glyph)
    const glyphs = (
      ['match', 'needs_review', 'mismatch', 'not_compared', 'present'] as Outcome[]
    ).map((outcome) => presentation(outcome).glyph)
    expect(new Set(glyphs).size).toBe(glyphs.length)
  })

  it('renders the word and a shape, so it survives with no colour at all', () => {
    render(<OutcomeBadge outcome="present" />)

    expect(screen.getByText('Contains')).toBeInTheDocument()
    expect(document.querySelector('.badge--match svg')).not.toBeNull()
  })
})

describe('the row', () => {
  it('shows the value found on the label', () => {
    render(<ResultCard field={presenceRow()} warning={warningDetail()} />)

    expect(screen.getByText('42% ALC BY VOL')).toBeInTheDocument()
  })

  it('shows no application side at all', () => {
    render(<ResultCard field={presenceRow()} warning={warningDetail()} />)

    // Not "Not supplied", and not the same string twice. There is nothing on
    // that side, so there is no row for it.
    expect(screen.queryByText(/On the application/)).not.toBeInTheDocument()
    expect(screen.queryByText('Not supplied')).not.toBeInTheDocument()
  })

  it('still shows an application side on a two-sided comparison', () => {
    render(
      <ResultCard
        field={field('alcohol_content', 'match', { application_value: '42%' })}
        warning={warningDetail()}
      />,
    )

    expect(screen.getByText(/On the application/)).toBeInTheDocument()
  })

  it('cites the regulation the check answered', () => {
    render(<ResultCard field={presenceRow()} warning={warningDetail()} />)

    expect(screen.getByText(/27 CFR 5\.63\(a\)\(3\)/)).toBeInTheDocument()
  })
})

describe('the tally', () => {
  it('counts presence checks alongside comparisons', () => {
    const outcomes: Outcome[] = ['match', 'match', 'present', 'present', 'match']

    expect(summary(outcomes)).toBe('5 of 5 checks passed')
  })

  it('a presence check that failed reduces the numerator', () => {
    const outcomes: Outcome[] = ['match', 'match', 'present', 'mismatch', 'match']

    expect(summary(outcomes)).toBe('4 of 5 checks passed')
  })

  it('still holds an artwork-derived row out of the count', () => {
    // Narrowed by ADR 0018 rather than removed: a field with no presence rule,
    // read off the artwork, on a submission with no photograph.
    const outcomes: Outcome[] = ['match', 'artwork_derived', 'present', 'present', 'match']

    expect(summary(outcomes)).toBe('4 of 4 checks passed; 1 read from the artwork only')
  })

  it('says in full what a listener cannot see on the chip', () => {
    const spoken = announcement(['match', 'match', 'present', 'present', 'match'])

    expect(spoken).toContain('5 of 5 checks passed.')
    expect(spoken).toContain('on the label as the regulation requires')
  })
})

/**
 * One batch row carrying exactly these five outcomes.
 *
 * Five, not two: the fixture pads a short list with matches, and a row padded
 * with matches cannot show what a row of nothing but presence checks reports.
 */
function row(outcomes: Outcome[]): BatchLine {
  return batchLine('0001-label.png', 1, 1, outcomes)
}

const ALL_PRESENT: Outcome[] = ['present', 'present', 'present', 'present', 'present']

describe('a batch row', () => {
  it('is a pass when a comparison and a presence check both passed', () => {
    expect(rowOutcome(row(['match', 'present', 'present', 'match', 'match']))).toBe('match')
  })

  it('reports Contains where nothing was compared but everything was found', () => {
    // A row of nothing but presence checks did not compare anything, so
    // claiming "Match" for it would assert an agreement it never tested.
    expect(rowOutcome(row(ALL_PRESENT))).toBe('present')
  })

  it('is never reported better than its worst field', () => {
    expect(rowOutcome(row(['present', 'mismatch', 'present', 'present', 'present']))).toBe(
      'mismatch',
    )
    expect(rowOutcome(row(['present', 'needs_review', 'present', 'present', 'present']))).toBe(
      'needs_review',
    )
  })
})
