/**
 * NFR-5's fourth criterion, as arithmetic: "Text contrast meets 4.5:1 for body
 * text."
 *
 * This exists alongside the axe run, not instead of it, and the two check
 * different things. axe checks what the built page actually renders, including
 * anything a later stylesheet change breaks. This checks the palette itself,
 * against every surface it is used on, whether or not a component happens to
 * combine them today. A token that has not been put on a page yet is exactly
 * the one that will fail later.
 *
 * The ratios are computed from index.css rather than from a table copied out of
 * it. A copy is a second source of truth and it goes stale silently.
 */
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// Resolved from the project root rather than from `import.meta.url`: under the
// jsdom environment that is an http URL, and `fileURLToPath` rejects it.
const CSS = readFileSync(resolve(process.cwd(), 'src/index.css'), 'utf-8')

/** The stylesheet with its comments removed, for assertions about declarations. */
const DECLARATIONS = CSS.replace(/\/\*[\s\S]*?\*\//g, '')

/** WCAG 2.1 relative luminance, from the definition in the specification. */
function luminance(hex: string): number {
  const value = hex.replace('#', '')
  const channels = [0, 2, 4].map((offset) => {
    const channel = parseInt(value.slice(offset, offset + 2), 16) / 255
    return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
}

function ratio(foreground: string, background: string): number {
  const a = luminance(foreground)
  const b = luminance(background)
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)
}

/** Read a custom property's value straight out of the stylesheet. */
function token(name: string): string {
  const match = CSS.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6})`))
  if (!match) throw new Error(`index.css does not define --${name}`)
  return match[1]
}

const AA_BODY = 4.5
/** WCAG 1.4.11: a focus indicator and other non-text UI need 3:1. */
const AA_NON_TEXT = 3

describe('every colour pair the interface can produce meets WCAG 2.1 AA', () => {
  const surfaces = ['page', 'surface']

  it.each(
    surfaces.flatMap((surface) =>
      ['text', 'text-muted', 'accent', 'match', 'review', 'mismatch', 'neutral'].map(
        (foreground) => [foreground, surface] as const,
      ),
    ),
  )('--%s on --%s is at least 4.5:1', (foreground, surface) => {
    expect(ratio(token(foreground), token(surface))).toBeGreaterThanOrEqual(AA_BODY)
  })

  it.each([
    ['match', 'match-tint'],
    ['review', 'review-tint'],
    ['mismatch', 'mismatch-tint'],
    ['neutral', 'neutral-tint'],
  ])('--%s on its own tint --%s is at least 4.5:1', (foreground, tint) => {
    expect(ratio(token(foreground), token(tint))).toBeGreaterThanOrEqual(AA_BODY)
  })

  it.each([
    ['text', 'match-tint'],
    ['text', 'review-tint'],
    ['text', 'mismatch-tint'],
    ['text', 'neutral-tint'],
  ])('body text --%s stays readable on the tinted card --%s', (foreground, tint) => {
    expect(ratio(token(foreground), token(tint))).toBeGreaterThanOrEqual(AA_BODY)
  })

  it('the primary button label is readable on its own background', () => {
    expect(ratio('#ffffff', token('accent'))).toBeGreaterThanOrEqual(AA_BODY)
  })

  it('the focus ring is visible against both surfaces', () => {
    for (const surface of surfaces) {
      expect(ratio(token('focus'), token(surface))).toBeGreaterThanOrEqual(AA_NON_TEXT)
    }
  })

  it('does not hand the background colour to the browser', () => {
    // `color-scheme: light dark` would make the contrast ratios above a
    // property of the visitor's settings rather than of this stylesheet, and
    // every assertion here would be measuring a palette that is not on screen.
    // Matched against the declarations rather than the file, so the comment
    // in index.css explaining why this is absent does not satisfy the check.
    expect(DECLARATIONS).not.toMatch(/color-scheme\s*:/)
  })
})
