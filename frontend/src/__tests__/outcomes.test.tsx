/**
 * Outcome rendering: text, shape and colour, and the needs-review distinction.
 *
 * Requirements: FR-10 (each row shows the field name, the label value, the
 * application value and the outcome; the outcomes are distinguishable without
 * relying on colour alone; needs-review is visually distinct from both match
 * and mismatch), NFR-5 (text and shape, not colour alone), FR-6 and OOS-4 (the
 * warning's capitalization is reported separately and the bold-type note is
 * repeated verbatim). Stories: US-2, US-13.
 */
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OutcomeBadge } from '../components/OutcomeBadge'
import { ResultCard } from '../components/ResultCard'
import { BOLD_TYPE_NOTE, field, warningDetail } from './fixtures'
import type { Outcome } from '../types'

describe('an outcome is carried by text and shape, not by colour', () => {
  const cases: [Outcome, string][] = [
    ['match', 'Match'],
    ['needs_review', 'Needs review'],
    ['mismatch', 'Does not match'],
    ['not_compared', 'Not compared'],
    ['artwork_derived', 'Read from the artwork'],
  ]

  it.each(cases)('%s renders the word "%s"', (outcome, word) => {
    render(<OutcomeBadge outcome={outcome} />)
    expect(screen.getByText(word)).toBeInTheDocument()
  })

  it('gives every outcome a different shape, not one shape recoloured', () => {
    const shapes = cases.map(([outcome]) => {
      const { container, unmount } = render(<OutcomeBadge outcome={outcome} />)
      const path = container.querySelector('svg path')?.getAttribute('d')
      unmount()
      return path
    })
    expect(shapes.every(Boolean)).toBe(true)
    expect(new Set(shapes).size).toBe(cases.length)
  })

  it('hides the icon from assistive technology, because the word says the same thing', () => {
    const { container } = render(<OutcomeBadge outcome="match" />)
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })

  it('reads an outcome this build does not know as not compared, never as a match', () => {
    render(<OutcomeBadge outcome={'something_new' as Outcome} />)
    expect(screen.getByText('Not compared')).toBeInTheDocument()
    expect(screen.queryByText('Match')).not.toBeInTheDocument()
  })
})

describe('a result card shows all four things FR-10 requires', () => {
  it('shows the field name, the label value, the application value and the outcome', () => {
    render(
      <ResultCard
        field={field('brand_name', 'match', {
          display_name: 'Brand name',
          label_value: "STONE'S THROW",
          application_value: "Stone's Throw",
          reason: 'Case and punctuation differences are ignored.',
        })}
      />,
    )
    expect(screen.getByRole('heading', { name: 'Brand name' })).toBeInTheDocument()
    expect(screen.getByText("STONE'S THROW")).toBeInTheDocument()
    expect(screen.getByText("Stone's Throw")).toBeInTheDocument()
    expect(screen.getByText('Match')).toBeInTheDocument()
    // FR-3: the evidence is shown so an agent can judge the call.
    expect(screen.getByText('Case and punctuation differences are ignored.')).toBeInTheDocument()
  })

  it('says a field was not found on the label rather than leaving it blank', () => {
    render(
      <ResultCard
        field={field('net_contents', 'not_compared', {
          found_on_label: false,
          label_value: null,
          application_value: null,
        })}
      />,
    )
    expect(screen.getByText('Not found on the label')).toBeInTheDocument()
    expect(screen.getByText('Not supplied')).toBeInTheDocument()
  })

  it('makes needs-review distinct from both match and mismatch', () => {
    const classFor = (outcome: Outcome) => {
      const { container, unmount } = render(<ResultCard field={field('brand_name', outcome)} />)
      const className = container.querySelector('article')!.className
      unmount()
      return className
    }
    const [match, review, mismatch] = (['match', 'needs_review', 'mismatch'] as Outcome[]).map(
      classFor,
    )

    expect(review).not.toBe(match)
    expect(review).not.toBe(mismatch)
    expect(review).toContain('card--review')
  })
})

describe('the government warning card', () => {
  it('reports capitalization separately from the wording (FR-6)', () => {
    render(
      <ResultCard
        field={field('government_warning', 'mismatch', {
          display_name: 'Government warning statement',
          reason: 'The statement wording matches the regulation.',
        })}
        warning={warningDetail({
          prefix_is_capitalized: false,
          prefix_as_printed: 'Government Warning:',
        })}
      />,
    )
    const card = screen.getByRole('article')
    expect(
      within(card).getByRole('heading', { name: 'Capitalization of the prefix' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/not in capital letters/)).toBeInTheDocument()
    expect(screen.getByText(/Government Warning:/)).toBeInTheDocument()
  })

  it('repeats the bold-type note verbatim rather than paraphrasing it (OOS-4)', () => {
    render(<ResultCard field={field('government_warning', 'match')} warning={warningDetail()} />)
    expect(screen.getByText(BOLD_TYPE_NOTE)).toBeInTheDocument()
  })

  it('does not claim a capitalization result when no statement was found', () => {
    render(
      <ResultCard
        field={field('government_warning', 'mismatch')}
        warning={warningDetail({
          statement_found: false,
          prefix_as_printed: null,
          prefix_is_capitalized: null,
          body_matches_regulation: false,
        })}
      />,
    )
    expect(screen.getByText(/no prefix to check/)).toBeInTheDocument()
  })
})

describe('the bold-type note appears once, not twice', () => {
  it('drops the API-appended copy from the reason, keeping the labelled section', () => {
    render(
      <ResultCard
        field={field('government_warning', 'mismatch', {
          reason: `The prefix is not in capital letters. ${BOLD_TYPE_NOTE}`,
        })}
        warning={warningDetail({ prefix_is_capitalized: false })}
      />,
    )
    expect(screen.getAllByText(BOLD_TYPE_NOTE)).toHaveLength(1)
    expect(screen.getByText('The prefix is not in capital letters.')).toBeInTheDocument()
  })

  it('keeps the note in the reason if the server wording has moved on', () => {
    render(
      <ResultCard
        field={field('government_warning', 'mismatch', {
          reason: 'The prefix is not in capital letters. Some newer note about bold type.',
        })}
        warning={warningDetail({ prefix_is_capitalized: false })}
      />,
    )
    expect(
      screen.getByText(/The prefix is not in capital letters\. Some newer note about bold type\./),
    ).toBeInTheDocument()
  })
})
