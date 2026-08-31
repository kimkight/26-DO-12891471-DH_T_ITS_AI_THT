/**
 * The application-side fields, and what the interface says about a gap in them
 * (US-26, FR-13).
 *
 * Separated from the component for the reason `photos.ts` and
 * `applicationSources.ts` are: these are decisions about which fields exist, in
 * what order, and what a missing one is called, and they are worth asserting
 * without rendering anything.
 */
import { EMPTY_APPLICATION } from '../types'
import type { ApplicationData, ApplicationSource } from '../types'

/** The four compared values, in the order a COLA application prints them. */
export const TEXT_FIELDS: {
  name: keyof ApplicationData
  label: string
  hint?: string
}[] = [
  { name: 'brand_name', label: 'Brand name' },
  { name: 'class_type', label: 'Class or type designation' },
  { name: 'alcohol_content', label: 'Alcohol content', hint: 'For example 45% or 45' },
  { name: 'net_contents', label: 'Net contents', hint: 'For example 750 mL' },
]

/** The three classes 27 CFR names. Kept in the words a label reviewer uses. */
export const BEVERAGE_TYPES = [
  { value: '', label: 'Choose one' },
  { value: 'distilled spirits', label: 'Distilled spirits' },
  { value: 'wine', label: 'Wine' },
  { value: 'malt beverage', label: 'Malt beverage' },
]

/**
 * The id of the panel the disclosure controls. A constant rather than `useId`
 * because it is referenced from `aria-controls` and from the toggle in the same
 * component, and a stable string is easier to read in a failing test.
 */
export const TYPED_FIELDS_PANEL = 'typed-application-values'

export type SourceMap = Partial<Record<keyof ApplicationData, ApplicationSource>>

/**
 * The application values to send with the check: the agent's own, and no others
 * (FR-11, FR-14, ADR 0013).
 *
 * **A value the interface filled in from the document is not a value the agent
 * typed, and posting it back as one destroys the only record of where it came
 * from.** The five boxes are a confirmation surface (US-24): uploading a COLA
 * writes what the server read out of it into them, sources and all, and the
 * agent may then edit any of them. Sending the whole set back with the check
 * arrives at the server as five typed values, because a typed part is what a
 * typed value is. `resolve_application` then records every one of them as
 * `typed`, which is the top of ADR 0010's precedence and the strongest claim
 * the response can make about a value.
 *
 * On a submission carrying only the application document that is not a
 * cosmetic error. FR-14's circularity overlay fires when the application value
 * was read off the same artwork that is standing in as the label side, so a
 * value laundered into `typed` on the way out of the browser is a value the
 * overlay cannot see. Measured against the deployed build on 2026-08-30 with
 * the author's own filing: the alcohol content and the net contents came back
 * as matches, the panel read "2 of 5 fields match", and both rows were one
 * reading of one picture compared with itself. The API returns them correctly
 * as `artwork_derived` when the browser sends nothing; it is the round trip
 * that breaks it, which is why the accessibility fixture, which stubs the
 * endpoint, could not see this.
 *
 * So the browser sends what the agent typed and lets the server re-derive the
 * rest from the document it is being sent anyway. Nothing is lost by that: the
 * server reads the same file with the same function, so a withheld value comes
 * back identical with its provenance intact. A value the agent edits becomes
 * theirs the moment they touch it, and is sent.
 */
export function typedValues(application: ApplicationData, sources: SourceMap): ApplicationData {
  const sent = { ...EMPTY_APPLICATION }
  for (const name of Object.keys(sent) as (keyof ApplicationData)[]) {
    if (sources[name] === 'typed') sent[name] = application[name]
  }
  return sent
}

/** The gap sentence for one field, in the words the agent needs to act. */
export function gapReason(label: string): string {
  return `${label} was not found in your upload. Enter it, or upload a clearer image.`
}

/**
 * The sentence announced when a processed upload left gaps.
 *
 * The field names arrive lower case so they read as English in the middle of a
 * list, and the sentence is capitalized at the end rather than the names at the
 * start, which is what keeps "alcohol content and net contents" from becoming
 * "Alcohol content and Net contents".
 */
export function gapAnnouncement(labels: string[]): string {
  if (!labels.length) return ''
  const sentence =
    labels.length === 1
      ? gapReason(labels[0])
      : `${labels.slice(0, -1).join(', ')} and ${labels[labels.length - 1]} were not found in ` +
        'your upload. Enter them, or upload a clearer image.'
  return `${sentence.charAt(0).toUpperCase()}${sentence.slice(1)}`
}
