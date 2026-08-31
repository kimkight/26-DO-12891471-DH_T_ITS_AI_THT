/**
 * What the interface says about a check that was made by searching (ADR 0015).
 *
 * The API asks whether each declared value appears on the label rather than
 * extracting a value and comparing two strings. A hit establishes that the text
 * is on the label; it does not establish that the text is there *as* the brand,
 * in the type size 27 CFR requires, or on the panel it belongs on. Type size and
 * placement are OOS-5 and are not checked at all.
 *
 * **That limit is said once, on the screen, and it is not optional.** The claim
 * the tool now makes is weaker than the one the old design implied, and a weaker
 * claim stated plainly is worth more than a stronger one nobody can check. It is
 * one line rather than a paragraph on every row, for the reason the author gave
 * about the rest of the screen: a sentence repeated five times is read nought
 * times.
 */

/**
 * The API's own wording, mirrored here so the row can print the rest of its
 * reason without repeating this line under it.
 *
 * It is duplicated rather than fetched because it is one sentence and adding a
 * field to the response to carry it would be machinery for a constant. The
 * duplication is safe in the one direction that matters: `reasonWithoutLimit`
 * removes it only on an exact match, so a server whose wording has moved on
 * keeps its own sentence in the row rather than losing it.
 */
export const PRESENCE_LIMIT =
  'This shows the declared value appears on the label. It does not show it ' +
  'appears as the brand, in the required type size, or on the required panel ' +
  '(OOS-5).'

/** The reason with the limit sentence taken off, where the API appended it. */
export function reasonWithoutLimit(reason: string): string {
  return reason.endsWith(PRESENCE_LIMIT) ? reason.slice(0, -PRESENCE_LIMIT.length).trim() : reason
}

/** Whether any row on this result was decided by searching the label. */
export function anySearched(reasons: string[]): boolean {
  return reasons.some((reason) => reason.endsWith(PRESENCE_LIMIT))
}
