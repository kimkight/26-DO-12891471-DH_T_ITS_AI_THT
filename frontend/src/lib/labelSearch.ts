/**
 * What the interface says about a check that was made by searching (ADR 0015).
 *
 * The API asks whether each declared value appears on the label rather than
 * extracting a value and comparing two strings. A hit establishes that the text
 * is on the label; it does not establish that the text is there *as* the brand,
 * in the type size 27 CFR requires, or on the panel it belongs on. Type size and
 * placement are OOS-5 and are not checked at all.
 *
 * **That limit is stated, and it is not optional.** The claim the tool makes is
 * weaker than the one the old design implied, and a weaker claim stated plainly
 * is worth more than a stronger one nobody can check.
 *
 * **Where it is stated moved on 2026-09-01** (US-28). It was a line above the
 * result rows, once rather than five times, which was already the second
 * shortening of it. It is now a Help entry, "Why is the brand name found but
 * not judged for type size or placement?", because it is the same sentence on
 * every check an agent ever runs, and a caveat printed on every check is read on
 * none of them. Nothing about the claim changed; it is answered where a question
 * is answered rather than asserted where work is done.
 *
 * `reasonWithoutLimit` still runs, and that is the part that must not be
 * removed with it: the API appends this sentence to every searched row's reason,
 * because a caller with no interface has nowhere else to read it, and without
 * the strip it would arrive on each row by the back door.
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

/**
 * Whether any row on this result was decided by searching the label.
 *
 * Nothing on the check screen calls this since the limit moved to Help (US-28).
 * It is kept because it is the one honest test of "did a search decide this
 * result", it is asserted in `verifyBySearch.test.tsx`, and a future surface
 * that wants to say something about searched rows should ask this rather than
 * re-deriving it from a string comparison of its own.
 */
export function anySearched(reasons: string[]): boolean {
  return reasons.some((reason) => reason.endsWith(PRESENCE_LIMIT))
}
