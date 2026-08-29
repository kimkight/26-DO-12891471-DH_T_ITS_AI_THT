/**
 * The application-side fields, and what the interface says about a gap in them
 * (US-26, FR-13).
 *
 * Separated from the component for the reason `photos.ts` and
 * `applicationSources.ts` are: these are decisions about which fields exist, in
 * what order, and what a missing one is called, and they are worth asserting
 * without rendering anything.
 */
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
