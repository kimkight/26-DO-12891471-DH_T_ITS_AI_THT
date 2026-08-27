/**
 * The line between reflecting an agency's design language and impersonating the
 * agency, enforced as tests rather than left to judgement.
 *
 * The interface is dressed in federal design language on purpose: the tool is
 * about federal label compliance, and a prototype that looked like a consumer
 * app would be answering the wrong question about whether it belongs in this
 * workflow. What makes that legitimate rather than a forgery is the set of
 * things it refuses to do, and a refusal that lives only in a person's memory
 * is a refusal that lasts one revision.
 *
 * So this file asserts both halves:
 *
 * 1. The disclosures are present, in the words they were written in, in the
 *    positions that make them read first.
 * 2. Nothing that would make the page read as an official government system is
 *    anywhere in the source: no seal, no eagle, no Treasury or TTB emblem, no
 *    "official website of the United States government" banner.
 *
 * The second half is a scan over the source files rather than over one rendered
 * component, because the failure it guards against is a future change adding an
 * asset somewhere this test does not render.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../App'

const ROOT = process.cwd()

/**
 * Every source file the built page is assembled from, tests excluded.
 *
 * Tests are excluded because this file, and any future one like it, has to
 * contain the forbidden strings in order to forbid them. A scan that included
 * itself could only ever fail.
 */
function sourceFiles(directory: string, found: string[] = []): string[] {
  for (const entry of readdirSync(directory)) {
    if (entry === '__tests__') continue
    const path = join(directory, entry)
    if (statSync(path).isDirectory()) {
      sourceFiles(path, found)
    } else if (/\.(tsx?|css|html|svg)$/.test(entry)) {
      found.push(path)
    }
  }
  return found
}

/**
 * A source file with its comments removed.
 *
 * The guard is about what the page renders, and a comment renders nothing. The
 * comments in `App.tsx` and `index.css` explain exactly which marks are
 * forbidden and therefore name every one of them; scanning the raw text would
 * make the explanation of the rule a violation of it, which would leave the
 * only options as deleting the explanation or deleting the test.
 */
function rendered(path: string): string {
  return readFileSync(path, 'utf-8')
    .replace(/\/\*[\s\S]*?\*\//g, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/^\s*\/\/.*$/gm, ' ')
}

const SOURCES = [...sourceFiles(resolve(ROOT, 'src')), resolve(ROOT, 'index.html')]
const ALL_SOURCE = SOURCES.map(rendered).join('\n')

describe('the prototype says what it is, before it says anything else', () => {
  it('carries the prototype banner, in the words it was written in', () => {
    const { container } = render(<App />)
    const banner = container.querySelector('.prototype-banner__text')
    expect(banner).toHaveTextContent(
      'Prototype built for an employment assessment. ' +
        'Not an official TTB or Treasury system. Nothing you upload is stored.',
    )
  })

  it('puts that banner ahead of the masthead in the document, so it reads first', () => {
    const { container } = render(<App />)
    const banner = container.querySelector('.prototype-banner')
    const masthead = container.querySelector('.masthead')
    expect(banner).not.toBeNull()
    expect(masthead).not.toBeNull()
    // Node.compareDocumentPosition: 4 means the argument follows the receiver.
    expect(banner!.compareDocumentPosition(masthead!) & Node.DOCUMENT_POSITION_FOLLOWING).toBe(
      Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })

  it('is not dismissible, because a prototype does not stop being one', () => {
    const { container } = render(<App />)
    const banner = container.querySelector('.prototype-banner')!
    expect(within(banner as HTMLElement).queryByRole('button')).toBeNull()
  })

  it('names the author and the assignment in the footer', () => {
    render(<App />)
    expect(
      screen.getByText('Built by Kimberly D. Kight as a take-home assignment.'),
    ).toBeInTheDocument()
  })

  it('names the product, with the agency as plain text rather than a wordmark', () => {
    render(<App />)
    expect(
      screen.getByRole('heading', { name: 'TTB Label Verifier', level: 1 }),
    ).toBeInTheDocument()
    expect(screen.getByText('Alcohol and Tobacco Tax and Trade Bureau')).toBeInTheDocument()
  })

  it('says "prototype" in the document title, which the page banner cannot reach', () => {
    const html = readFileSync(resolve(ROOT, 'index.html'), 'utf-8')
    expect(html).toMatch(/<title>[^<]*prototype[^<]*<\/title>/i)
  })
})

describe('the interface does not impersonate a government system', () => {
  /*
   * Phrases that would turn a design-language homage into a claim of
   * officialdom. The first is the exact banner every federal site carries; the
   * rest are the ways a seal or emblem tends to arrive, usually as a filename
   * or an alt attribute rather than as visible copy.
   */
  const FORBIDDEN = [
    /official website of the United States government/i,
    /an official website/i,
    /\bgreat seal\b/i,
    /\bttb[-_ ]?seal\b/i,
    /\btreasury[-_ ]?seal\b/i,
    /\bagency[-_ ]?seal\b/i,
    /\bcoat of arms\b/i,
    /\beagle\b/i,
    /\bofficial[-_ ]?seal\b/i,
  ]

  it.each(FORBIDDEN)('nothing the page renders contains %s', (pattern) => {
    const offenders = SOURCES.filter((path) => pattern.test(rendered(path)))
    expect(offenders).toEqual([])
  })

  it('carries no seal, emblem or logo image anywhere in the source', () => {
    // No raster or vector asset is imported at all. The only SVG in the
    // interface is drawn inline by OutcomeBadge, which is four geometric
    // shapes carrying the four outcomes (FR-10) and no mark of any kind.
    expect(ALL_SOURCE).not.toMatch(/\.(png|jpe?g|gif|webp|ico)['")]/i)
    expect(ALL_SOURCE).not.toMatch(/from\s+['"][^'"]+\.svg['"]/i)
  })

  it('puts no image in the masthead or the footer, which is where a seal would go', () => {
    const { container } = render(<App />)
    for (const selector of ['.masthead', '.site-footer']) {
      const region = container.querySelector(selector)!
      expect(region.querySelector('img')).toBeNull()
      expect(region.querySelector('svg')).toBeNull()
    }
  })

  it('claims no authority: nothing approves, certifies, or issues a determination', () => {
    render(<App />)
    const page = document.body.textContent ?? ''
    for (const word of [/\bapproved\b/i, /\bcertifie/i, /\bofficial determination\b/i]) {
      expect(page).not.toMatch(word)
    }
    // What it says instead, on screen rather than only in a document.
    expect(page).toMatch(/This tool recommends\. You decide\./)
  })
})
