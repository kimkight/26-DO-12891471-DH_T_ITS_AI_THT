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
export type Glyph = 'check' | 'triangle' | 'cross' | 'dash' | 'artwork'

export interface OutcomePresentation {
  /** The word an agent reads. Plain language, no jargon (NFR-4). */
  label: string
  glyph: Glyph
  tone: 'match' | 'review' | 'mismatch' | 'neutral' | 'artwork'
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
  /*
   * FR-14, ADR 0013. Not a verdict, and worded so that it cannot be read as
   * one: "Read from the artwork" says what happened rather than how it went.
   * Its own silhouette, a picture frame, because it is a statement about where
   * a value came from and none of the other four shapes means that. The colour
   * arrives last here as everywhere else, and the word alone is enough.
   */
  artwork_derived: {
    label: 'Read from the artwork',
    glyph: 'artwork',
    tone: 'artwork',
    spoken: 'was read from the label artwork and could not be compared against it',
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
    artwork_derived: 0,
  }
  for (const outcome of outcomes) {
    if (outcome in counts) counts[outcome] += 1
  }
  return counts
}

/**
 * The summary line, which stops claiming a denominator it does not have
 * (FR-14, ADR 0013).
 *
 * **"5 of 5 fields match" was the false half of the old line.** On a submission
 * where the agent uploaded only the application document, some of those five
 * rows compared a value read off the label artwork against that same artwork.
 * Counting them alongside the rows that were genuinely checked inflates the
 * denominator with fields that could not have come out any other way, which is
 * exactly the false assurance the artwork-derived state exists to prevent.
 *
 * So the count is over the verifiable rows only, and the rows that were merely
 * read are stated beside it rather than hidden: "3 of 3 verifiable fields
 * match; 2 read from the artwork only". Where nothing was artwork-derived,
 * which is every submission carrying a photograph, the second clause is absent
 * and the word "verifiable" with it: the line reads as it always did, because
 * there is nothing to qualify.
 */
export function summary(outcomes: Outcome[]): string {
  const counts = tally(outcomes)
  const derived = counts.artwork_derived
  const verifiable = outcomes.length - derived
  if (derived === 0) {
    return `${counts.match} of ${outcomes.length} fields match`
  }
  const noun = verifiable === 1 ? 'verifiable field' : 'verifiable fields'
  const verb = verifiable === 1 ? 'matches' : 'match'
  return (
    `${counts.match} of ${verifiable} ${noun} ${verb}; ` + `${derived} read from the artwork only`
  )
}

/**
 * The sentence read out when results appear (NFR-5's last criterion).
 *
 * Written as a sentence rather than as a count list because it is heard, not
 * scanned. "Three fields match" is followed by only what needs attention, so
 * the important half is not buried behind four zeroes.
 *
 * It opens with the same summary the panel prints, so what is heard and what is
 * seen are one sentence rather than two that can drift apart.
 */
export function announcement(outcomes: Outcome[], seconds: number): string {
  const counts = tally(outcomes)
  const parts = [`Checked in ${seconds.toFixed(1)} seconds.`]
  parts.push(`${summary(outcomes)}.`)
  if (counts.needs_review > 0) {
    parts.push(`${counts.needs_review} needs your review.`)
  }
  if (counts.mismatch > 0) {
    parts.push(`${counts.mismatch} does not match.`)
  }
  if (counts.not_compared > 0) {
    parts.push(`${counts.not_compared} was not compared.`)
  }
  if (counts.artwork_derived > 0) {
    parts.push(
      `${counts.artwork_derived} came from the label artwork inside the application, ` +
        'so there was nothing independent to check it against.',
    )
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
  // Ranked below "not compared" rather than above it, because the two say
  // different things and neither is a match: "not compared" is a field with no
  // evidence at all, and this is a field with evidence that could not disagree.
  // A row carrying one is never reported as fully matching (FR-14, ADR 0013).
  if (outcomes.includes('artwork_derived')) return 'artwork_derived'
  return 'match'
}

/** How many of a row's fields carry one outcome, for the table's count columns. */
export function countOf(line: BatchLine, outcome: Outcome): number {
  if (!line.result) return 0
  return line.result.fields.filter((field) => field.outcome === outcome).length
}
