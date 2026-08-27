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
      [
        'text',
        'text-muted',
        'accent',
        'accent-dark',
        'gold-text',
        'match',
        'review',
        'mismatch',
        'neutral',
      ].map((foreground) => [foreground, surface] as const),
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

  /*
   * The masthead is the one dark surface in the interface, so the tokens that
   * appear on it are checked against it rather than against the light ones.
   * --gold-bright is brilliant on navy and illegible on white, which is why it
   * is not in the list above: it is checked where it is used.
   */
  it('everything on the navy masthead is readable against it', () => {
    expect(ratio('#ffffff', token('accent-dark'))).toBeGreaterThanOrEqual(AA_BODY)
    expect(ratio(token('gold-bright'), token('accent-dark'))).toBeGreaterThanOrEqual(AA_BODY)
  })

  it('the focus ring used on the navy masthead is visible against it', () => {
    expect(ratio(token('focus-on-dark'), token('accent-dark'))).toBeGreaterThanOrEqual(AA_NON_TEXT)
  })

  it('the prototype banner is readable, and its gold edge is visible on it', () => {
    expect(ratio(token('text'), token('notice'))).toBeGreaterThanOrEqual(AA_BODY)
    // The edge is a rule, not text, so 3:1 is the applicable minimum (1.4.11).
    expect(ratio(token('gold'), token('notice'))).toBeGreaterThanOrEqual(AA_NON_TEXT)
  })

  it('the gold rule and edges are visible against every surface they sit on', () => {
    for (const surface of [...surfaces, 'page']) {
      expect(ratio(token('gold'), token(surface))).toBeGreaterThanOrEqual(AA_NON_TEXT)
    }
  })

  /*
   * The mark on a field filled from an uploaded COLA document (FR-11). It is
   * text, so 4.5:1 applies, and it sits on the white panel and on the grey
   * surface of the upload block. Asserted through the class rather than only
   * through the token, so that changing the class to a colour that has not been
   * checked fails here.
   */
  it('the "read from the application form" mark uses a verified text colour', () => {
    const rule = CSS.match(/\.field__source\s*{[^}]*}/)
    expect(rule, 'index.css does not define .field__source').not.toBeNull()
    expect(rule![0]).toContain('var(--gold-text)')
    for (const surface of [...surfaces, 'shell']) {
      expect(ratio(token('gold-text'), token(surface))).toBeGreaterThanOrEqual(AA_BODY)
    }
  })

  /*
   * The shell is the grey field the white panels sit on. It is the same value
   * as --surface today and it is checked separately rather than assumed to
   * stay that way, because a change to one is not a change to the other.
   */
  it('body text is readable on the page shell', () => {
    expect(ratio(token('text'), token('shell'))).toBeGreaterThanOrEqual(AA_BODY)
    expect(ratio(token('text-muted'), token('shell'))).toBeGreaterThanOrEqual(AA_BODY)
  })

  /*
   * NFR-3 forbids an outbound network call on the default path, and the page is
   * part of that path. A font fetched from a CDN would make the interface break
   * on exactly the network Marcus Williams describes, and it would do so
   * silently: the page still renders, in a fallback face, on a firewall that
   * blocks the request. The font is a bundled dependency served from this
   * origin instead, so this asserts the stylesheet imports it rather than
   * linking out to one.
   */
  it('fetches no font, and no other asset, from an external origin (NFR-3)', () => {
    expect(DECLARATIONS).not.toMatch(/@import\s+url\(\s*['"]?https?:/i)
    expect(DECLARATIONS).not.toMatch(/url\(\s*['"]?https?:\/\//i)
    expect(DECLARATIONS).not.toMatch(/fonts\.(googleapis|gstatic)\.com/i)
    expect(DECLARATIONS).toMatch(/@import\s+'@fontsource-variable\/public-sans/)
  })

  it('names a fallback after the bundled font, so a missing file is not a blank page', () => {
    const stack = CSS.match(/font-family:\s*([^;]+);/)?.[1] ?? ''
    expect(stack).toMatch(/Public Sans Variable/)
    expect(stack).toMatch(/system-ui/)
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
