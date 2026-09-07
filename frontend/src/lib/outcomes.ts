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
export type Glyph = 'check' | 'triangle' | 'cross' | 'dash' | 'artwork' | 'carried' | 'look'

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
   * FR-15, ADR 0018. A passing one-sided finding, and the word carries the
   * whole of the difference from a match.
   *
   * **"Contains" is the stronger claim, not the weaker one.** "Match" says two
   * things agreed. Here one thing was found, and what it establishes is that the
   * label carries an element 27 CFR requires it to carry, which is exactly what
   * the agent is checking. Calling that a match would claim an agreement that
   * was never tested, on a row that has only one side.
   *
   * It is styled like a pass, in the same green as Match, because it is one. So
   * the shape has to do the separating, and it does: a ring with a dot inside
   * says "the label carries this", and no other outcome uses it. Under a
   * greyscale check Contains and Match differ by both word and silhouette,
   * which is what NFR-5 asks and what a shared colour makes load-bearing.
   *
   * If the author prefers the word "Match" here, this `label` is the one
   * constant to change; nothing else keys on the word.
   */
  present: {
    label: 'Contains',
    glyph: 'carried',
    tone: 'match',
    spoken: 'is on the label, as the regulation requires',
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
  /*
   * FR-5, ADR 0022. The government warning alone: it is on the label, it does
   * not match word for word, and every line that differs was read too poorly
   * to say whether the difference is the label's or the reading's. A failing
   * outcome, in the review tone because it is a person's next action, with
   * its own silhouette, a magnifier, because what it asks is "look at the
   * label", which no other outcome asks. The word says what was established
   * and what was not, in that order.
   */
  not_certified: {
    label: 'Present, not certified',
    glyph: 'look',
    tone: 'review',
    spoken: 'is on the label but could not be read cleanly enough to certify word for word',
  },
}

/**
 * Every outcome the interface can present, read off the definitions above.
 *
 * Exported so that a test checking every outcome (the contrast pairs, the
 * word-and-shape rule) walks this list rather than a copy of it kept beside
 * the test: a seventh outcome added with an unchecked tone then fails the test
 * instead of shipping (code review finding 7, criterion 1.4.3).
 */
export const OUTCOMES = Object.keys(PRESENTATIONS) as Outcome[]

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
    present: 0,
    artwork_derived: 0,
    not_certified: 0,
  }
  for (const outcome of outcomes) {
    if (outcome in counts) counts[outcome] += 1
  }
  return counts
}

/**
 * The summary line: how many checks passed, out of how many were made
 * (FR-15, ADR 0018; FR-14, ADR 0013).
 *
 * **It counts two kinds of check together, because there are two kinds.** A
 * comparison passes when the label agrees with what the application declared. A
 * presence check passes when the label carries an element 27 CFR requires and
 * the application declared nothing to compare it against. Both establish
 * something; neither is worth more than the other on the face of a summary
 * line; and an agent reading "5 of 5 checks passed" can see which row was which
 * from the chips underneath.
 *
 * It replaces "3 of 3 verifiable fields match; 2 read from the artwork only",
 * which was the honest line while those two rows were circular comparisons.
 * They are presence checks now, so they count, and the denominator is the whole
 * result again.
 *
 * **The artwork-derived clause survives, narrowed.** A row that really is one
 * reading of one picture compared with itself still establishes nothing, and it
 * still may not be counted as a check that passed. After ADR 0018 that is rare:
 * it needs a field with no presence rule, read off the artwork, on a submission
 * with no photograph. Where it happens the line says so rather than absorbing
 * it.
 */
export function summary(outcomes: Outcome[]): string {
  const { passed, checks, derived } = checksPassed(outcomes)
  const noun = checks === 1 ? 'check' : 'checks'
  const line = `${passed} of ${checks} ${noun} passed`
  if (derived === 0) return line
  return `${line}; ${derived} read from the artwork only`
}

/**
 * The numbers behind the summary line, so the batch table's Checks column
 * ("5 of 5") and the sentence under a result ("5 of 5 checks passed") are one
 * count and cannot disagree (ADR 0020).
 */
export function checksPassed(outcomes: Outcome[]): {
  passed: number
  checks: number
  derived: number
} {
  const counts = tally(outcomes)
  const derived = counts.artwork_derived
  return {
    passed: counts.match + counts.present,
    checks: outcomes.length - derived,
    derived,
  }
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
 *
 * **The elapsed time came out of it on 2026-08-31**, when it came off the screen.
 * That is the same rule and not a second one: an announcement that reads out a
 * number nobody can see is exactly the drift this docstring warns about, and
 * NFR-5 asks the announcement to say what changed, which is the outcomes. It
 * says no less about them than it did.
 */
export function announcement(outcomes: Outcome[]): string {
  const counts = tally(outcomes)
  const parts = [`${summary(outcomes)}.`]
  if (counts.needs_review > 0) {
    parts.push(`${counts.needs_review} needs your review.`)
  }
  if (counts.mismatch > 0) {
    parts.push(`${counts.mismatch} does not match.`)
  }
  if (counts.not_certified > 0) {
    // Said in full: the chip's words are not on offer to a listener, and what
    // this asks of them is different from what a review asks (ADR 0022).
    parts.push(
      'The government warning is on the label but could not be read cleanly enough ' +
        'to certify word for word; check the label itself.',
    )
  }
  if (counts.not_compared > 0) {
    parts.push(`${counts.not_compared} was not compared.`)
  }
  if (counts.present > 0) {
    // Said in full, because the chip's one word is not on offer to a listener.
    // What a presence check establishes is different from what a comparison
    // establishes, and an agent hearing the result is entitled to the
    // difference (FR-15, NFR-5).
    parts.push(
      `${counts.present} ${counts.present === 1 ? 'is' : 'are'} on the label as the ` +
        'regulation requires, with nothing declared on the application to compare against.',
    )
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
  // Between a mismatch and a review: failing, like both, and asking for the
  // label itself rather than a diff, which is more than a review asks
  // (ADR 0022).
  if (outcomes.includes('not_certified')) return 'not_certified'
  if (outcomes.includes('needs_review')) return 'needs_review'
  if (outcomes.includes('not_compared')) return 'not_compared'
  // Ranked below "not compared" rather than above it, because the two say
  // different things and neither is a match: "not compared" is a field with no
  // evidence at all, and this is a field with evidence that could not disagree.
  // A row carrying one is never reported as fully matching (FR-14, ADR 0013).
  if (outcomes.includes('artwork_derived')) return 'artwork_derived'
  // Every row passed. The chip says which kind of pass it was: a row of nothing
  // but presence checks did not compare anything, and claiming "Match" for it
  // would be the row asserting an agreement it never tested (FR-15, ADR 0018).
  return outcomes.includes('match') ? 'match' : 'present'
}

/** How many of a row's fields carry one outcome, for the table's count columns. */
export function countOf(line: BatchLine, outcome: Outcome): number {
  if (!line.result) return 0
  return line.result.fields.filter((field) => field.outcome === outcome).length
}

/**
 * The categories a batch row can land in, in the order the tally lists them,
 * with the words the tally uses (code review finding 16, #115).
 *
 * **They partition what `rowOutcome` returns**, which is what makes the tally
 * account for every row: a reader adding the seven counts gets the row count.
 * Until v1.3.0 the tally had four buckets, so a row whose worst outcome was
 * "not compared", "present" or "artwork-derived" was counted nowhere, and "0
 * fully matching, 0 needing review, 0 not matching, 0 could not be checked"
 * sat beside "1 of 1 labels checked". `present` is kept apart from `match` on
 * purpose: a presence row asserts no agreement (FR-15).
 */
export const ROW_BUCKETS: { outcome: Outcome | 'error'; label: string }[] = [
  { outcome: 'match', label: 'fully matching' },
  { outcome: 'present', label: 'passing on what the label carries, with nothing declared' },
  { outcome: 'needs_review', label: 'needing review' },
  { outcome: 'not_certified', label: 'with a warning present and not certified' },
  { outcome: 'mismatch', label: 'not matching' },
  { outcome: 'not_compared', label: 'with a value not compared' },
  { outcome: 'artwork_derived', label: 'read from the artwork only' },
  { outcome: 'error', label: 'could not be checked' },
]

/** One row's own summary line, in the words the single-label view uses. */
export function rowSummary(line: BatchLine): string {
  if (!line.result) return line.error?.message ?? ''
  const outcomes = line.result.fields.map((field) => field.outcome)
  const named = line.result.fields
    .filter((field) => field.outcome !== 'match')
    .map((field) => `${field.display_name} ${presentation(field.outcome).spoken}`)
  return [`${summary(outcomes)}.`, ...named.map((sentence) => `${sentence}.`)].join(' ')
}
