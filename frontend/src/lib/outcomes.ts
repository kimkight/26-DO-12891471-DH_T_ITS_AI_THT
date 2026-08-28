/**
 * How an outcome is presented: text, shape, and colour, in that order.
 *
 * Governing requirements: FR-10 (the three outcomes are distinguishable without
 * relying on colour alone, and fields needing human review are visually
 * distinct from both matches and mismatches), NFR-5 (outcomes are conveyed by
 * text and shape, not by colour alone).
 *
 * The ordering in that first sentence is the design rule. Every outcome carries
 * a word an agent can read, a shape that differs from every other shape, and
 * only then a colour. Removing the colour entirely would leave the interface
 * still usable, which is the test NFR-5 sets.
 *
 * `tone` is a class name suffix rather than a colour value. The colours live in
 * index.css as tokens, so contrast is defined in one place and checked in one
 * place (src/__tests__/contrast.test.ts).
 */
import type { BatchLine, Outcome } from '../types'

/** The shapes. Deliberately different silhouettes, not one shape recoloured. */
export type Glyph = 'check' | 'triangle' | 'cross' | 'dash'

export interface OutcomePresentation {
  /** The word an agent reads. Plain language, no jargon (NFR-4). */
  label: string
  glyph: Glyph
  tone: 'match' | 'review' | 'mismatch' | 'neutral'
  /** Expanded wording for the live region, where there is no icon to see. */
  spoken: string
}

const PRESENTATIONS: Record<Outcome, OutcomePresentation> = {
  match: {
    label: 'Match',
    glyph: 'check',
    tone: 'match',
    spoken: 'matches the application',
  },
  needs_review: {
    label: 'Needs review',
    glyph: 'triangle',
    tone: 'review',
    spoken: 'needs your review',
  },
  mismatch: {
    label: 'Does not match',
    glyph: 'cross',
    tone: 'mismatch',
    spoken: 'does not match the application',
  },
  not_compared: {
    label: 'Not compared',
    glyph: 'dash',
    tone: 'neutral',
    spoken: 'was not compared',
  },
}

export function presentation(outcome: Outcome): OutcomePresentation {
  // An unrecognized outcome presents as not compared rather than as a match.
  // FR-9's last criterion is that no error path reports a match, and a value
  // this build has not seen is closer to an error than to agreement.
  return PRESENTATIONS[outcome] ?? PRESENTATIONS.not_compared
}

/** Counts for the summary line and the live region announcement. */
export function tally(outcomes: Outcome[]): Record<Outcome, number> {
  const counts: Record<Outcome, number> = {
    match: 0,
    needs_review: 0,
    mismatch: 0,
    not_compared: 0,
  }
  for (const outcome of outcomes) {
    if (outcome in counts) counts[outcome] += 1
  }
  return counts
}

/**
 * The sentence read out when results appear (NFR-5's last criterion).
 *
 * Written as a sentence rather than as a count list because it is heard, not
 * scanned. "Three fields match" is followed by only what needs attention, so
 * the important half is not buried behind four zeroes.
 */
export function announcement(outcomes: Outcome[], seconds: number): string {
  const counts = tally(outcomes)
  const parts = [`Checked in ${seconds.toFixed(1)} seconds.`]
  parts.push(`${counts.match} of ${outcomes.length} fields match.`)
  if (counts.needs_review > 0) {
    parts.push(`${counts.needs_review} needs your review.`)
  }
  if (counts.mismatch > 0) {
    parts.push(`${counts.mismatch} does not match.`)
  }
  if (counts.not_compared > 0) {
    parts.push(`${counts.not_compared} was not compared.`)
  }
  return parts.join(' ')
}

/**
 * The worst outcome on a batch row, which is what its chip reports.
 *
 * A row is never presented as better than its worst field. An agent scanning
 * 300 rows for the ones needing attention has to be able to trust that a row
 * marked as a match has nothing in it to look at.
 *
 * Here rather than in the table component because the batch tab's summary
 * counts use the same rule, and two implementations of "how good is this row"
 * would eventually disagree.
 */
export function rowOutcome(line: BatchLine): Outcome | 'error' {
  if (line.status === 'error' || !line.result) return 'error'
  const outcomes = line.result.fields.map((field) => field.outcome)
  if (outcomes.includes('mismatch')) return 'mismatch'
  if (outcomes.includes('needs_review')) return 'needs_review'
  if (outcomes.includes('not_compared')) return 'not_compared'
  return 'match'
}

/** How many of a row's fields carry one outcome, for the table's count columns. */
export function countOf(line: BatchLine, outcome: Outcome): number {
  if (!line.result) return 0
  return line.result.fields.filter((field) => field.outcome === outcome).length
}
