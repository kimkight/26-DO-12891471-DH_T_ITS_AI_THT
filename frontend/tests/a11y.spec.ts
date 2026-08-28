/**
 * The automated accessibility check, run by axe-core against the built page.
 *
 * Requirement: NFR-5, "The interface targets WCAG 2.1 Level AA." Story: US-13.
 *
 * `axe-core` is injected into the page directly rather than through a wrapper
 * package. One dependency instead of two, and the version that runs is the one
 * in package.json rather than whatever a wrapper pins.
 *
 * **What this proves and what it does not.** axe finds a subset of WCAG
 * failures; a clean run is not a conformance claim, and no automated tool
 * replaces testing with an actual screen reader. What it does do is stop the
 * regressions that are cheap to introduce and expensive to notice: an input
 * that loses its label, a heading level skipped, a contrast pair broken by a
 * token change. The keyboard behaviour is asserted separately below, because
 * axe cannot check whether a control can actually be operated.
 */
import { expect, test } from '@playwright/test'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const AXE_PATH = require.resolve('axe-core/axe.min.js')

/** WCAG 2.1 Level AA and below, which is what NFR-5 names. */
const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

interface AxeViolation {
  id: string
  impact: string | null
  help: string
  nodes: { html: string; failureSummary?: string }[]
}

async function violations(page: import('@playwright/test').Page): Promise<AxeViolation[]> {
  await page.addScriptTag({ path: AXE_PATH })
  return page.evaluate(async (tags) => {
    // @ts-expect-error axe is attached to window by the injected script.
    const results = await window.axe.run(document, { runOnly: { type: 'tag', values: tags } })
    return results.violations.map(
      (violation: {
        id: string
        impact: string | null
        help: string
        nodes: { html: string; failureSummary?: string }[]
      }) => ({
        id: violation.id,
        impact: violation.impact,
        help: violation.help,
        nodes: violation.nodes.map((node) => ({
          html: node.html,
          failureSummary: node.failureSummary,
        })),
      }),
    )
  }, TAGS)
}

function report(found: AxeViolation[]): string {
  return found
    .map(
      (violation) =>
        `${violation.id} (${violation.impact}): ${violation.help}\n` +
        violation.nodes.map((node) => `    ${node.html}`).join('\n'),
    )
    .join('\n')
}

test.describe('WCAG 2.1 AA, checked by axe-core against the built page', () => {
  test('the landing page, which is the single-label task', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'TTB Label Verifier', level: 1 })).toBeVisible()
    const found = await violations(page)
    expect(report(found)).toBe('')
  })

  test('the batch tab', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('tab', { name: 'Check many labels' }).click()
    // Both pickers, and the pairing rule that says how they go together
    // (ADR 0009), are on the page rather than behind a disclosure.
    await expect(page.getByLabel('Label images')).toBeVisible()
    await expect(page.getByLabel('COLA documents')).toBeVisible()
    await expect(page.getByText(/They are matched by name/)).toBeVisible()
    const found = await violations(page)
    expect(report(found)).toBe('')
  })

  test('the batch pickers and the pairing count are reachable by keyboard', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('tab', { name: 'Check many labels' }).click()
    const panel = page.locator('#panel-batch')

    // Tab from the selected tab into the panel: the two pickers are the first
    // two stops, in reading order (NFR-5).
    await page.getByRole('tab', { name: 'Check many labels' }).focus()
    await page.keyboard.press('Tab')
    await expect(panel.getByLabel('Label images')).toBeFocused()
    await page.keyboard.press('Tab')
    await expect(panel.getByLabel('COLA documents')).toBeFocused()

    await panel.getByLabel('Label images').setInputFiles([
      { name: '0001-stones-throw.png', mimeType: 'image/png', buffer: Buffer.from([137, 80]) },
      { name: '0002-hollow-creek.png', mimeType: 'image/png', buffer: Buffer.from([137, 80]) },
    ])
    await panel
      .getByLabel('COLA documents')
      .setInputFiles([
        { name: '0001-STONES-THROW.pdf', mimeType: 'application/pdf', buffer: Buffer.from('%PDF') },
      ])

    // Announced through a live region, and visible, from one sentence.
    await expect(
      panel.getByText('1 pair ready to check, 1 image with no matching document.'),
    ).toBeVisible()
  })

  test('the results, including a needs-review card and an error notice', async ({ page }) => {
    // The results only exist after a response, so one is supplied here rather
    // than reaching the real API. The markup under test is the interface's.
    await page.route('**/api/verify', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(RESULT),
      })
    })
    await page.goto('/')
    await page.getByLabel('Label image').setInputFiles({
      name: 'label.png',
      mimeType: 'image/png',
      buffer: Buffer.from([137, 80, 78, 71]),
    })
    await page.getByRole('button', { name: 'Check this label' }).click()
    await expect(page.getByText(/Checked in/).first()).toBeVisible()

    const found = await violations(page)
    expect(report(found)).toBe('')
  })
})

test.describe('what axe cannot check', () => {
  test('every control is reachable by keyboard, and its focus is visible', async ({ page }) => {
    await page.goto('/')

    // The skip link is first, so an agent can get past the chrome (NFR-5).
    await page.keyboard.press('Tab')
    await expect(page.getByRole('link', { name: 'Skip to the label check' })).toBeFocused()

    // Then the selected tab. The unselected one is out of the tab order and
    // reached with an arrow key, which is the ARIA tabs pattern.
    await page.keyboard.press('Tab')
    await expect(page.getByRole('tab', { name: 'Check one label' })).toBeFocused()
    await page.keyboard.press('ArrowRight')
    await expect(page.getByRole('tab', { name: 'Check many labels' })).toBeFocused()
    await expect(page.getByRole('tab', { name: 'Check many labels' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    await page.keyboard.press('ArrowLeft')
    await expect(page.getByRole('tab', { name: 'Check one label' })).toBeFocused()

    // Then the file input, the control that adds a second photo of the same
    // label (ADR 0007), the COLA document upload, and the disclosure over the
    // typed fields, in reading order. The five fields themselves are behind
    // that disclosure and out of the tab order until it is opened (US-24),
    // which is the point of it.
    //
    // Scoped to the single-label panel. The arrow-key steps above mounted the
    // batch panel too, and it stays mounted so a half-filled form survives a
    // look at the other tab. It is `hidden`, so it is out of the tab order,
    // which is what the loop below proves by reaching these in sequence; but
    // an unscoped lookup would still match its controls by name.
    const panel = page.locator('#panel-single')
    await page.keyboard.press('Tab')
    await expect(panel.getByLabel('Label image', { exact: true })).toBeFocused()

    await page.keyboard.press('Tab')
    await expect(
      panel.getByRole('button', { name: 'Add another photo of this label' }),
    ).toBeFocused()

    // Then the COLA document upload, which is the primary application-side
    // input and sits directly after the photographs (FR-11, ADR 0008, US-24).
    await page.keyboard.press('Tab')
    await expect(panel.getByLabel('Label application', { exact: true })).toBeFocused()

    // Then the disclosure. Collapsed, so the next Tab from here reaches the
    // submit button rather than a field: five empty boxes are no longer what
    // an agent walks through to get to the check (NFR-4).
    const disclosure = panel.getByRole('button', { name: 'Or type the application values' })
    await page.keyboard.press('Tab')
    await expect(disclosure).toBeFocused()
    await expect(disclosure).toHaveAttribute('aria-expanded', 'false')

    // Visible focus on the control that is new to this walk, asserted while
    // the keyboard put the focus there so :focus-visible applies (NFR-5).
    const toggleOutline = await disclosure.evaluate(
      (element) => getComputedStyle(element).outlineWidth,
    )
    expect(parseFloat(toggleOutline)).toBeGreaterThan(0)

    const expected = [
      'Brand name',
      'Class or type designation',
      'Alcohol content',
      'Net contents',
      'Beverage type',
    ]

    // Collapsed, the five are out of the tab order because they are hidden,
    // not merely visually tucked away. That is the whole claim of the
    // disclosure: fewer things between an agent and the check (NFR-4).
    for (const label of expected) {
      await expect(panel.getByLabel(label, { exact: true })).toBeHidden()
    }

    // Opened from the keyboard, they are in the tab order in reading order,
    // with beverage type last because it is never compared.
    await page.keyboard.press('Enter')
    await expect(disclosure).toHaveAttribute('aria-expanded', 'true')

    for (const label of expected) {
      await page.keyboard.press('Tab')
      await expect(panel.getByLabel(label, { exact: true })).toBeFocused()
    }

    // A visible focus indicator, which axe cannot see (NFR-5's second
    // criterion). Asserted on the outline the stylesheet sets for
    // :focus-visible, which keyboard navigation triggers, on whichever control
    // the walk above ended on: beverage type, now that it is last.
    const outline = await panel
      .getByLabel('Beverage type', { exact: true })
      .evaluate((element) => getComputedStyle(element).outlineWidth)
    expect(parseFloat(outline)).toBeGreaterThan(0)
  })

  /*
   * The disclosures, checked in the built page rather than only in jsdom. What
   * a reviewer will look at is the deployed URL, and what is asserted here is
   * that the two things separating design-language homage from impersonation
   * survive the build: the banner is on screen before anything else, and the
   * masthead carries no seal or emblem of any kind.
   */
  test('the prototype banner and the author attribution are on the built page', async ({
    page,
  }) => {
    await page.goto('/')
    await expect(
      page.getByText(
        'Prototype built for an employment assessment. Not an official TTB or Treasury ' +
          'system. Nothing you upload is stored.',
      ),
    ).toBeVisible()
    await expect(
      page.getByText('Built by Kimberly D. Kight as a take-home assignment.'),
    ).toBeVisible()
    // No seal, emblem or wordmark image in the masthead.
    await expect(page.locator('.masthead img, .masthead svg')).toHaveCount(0)
  })

  test('the bundled font loads from this origin and nothing is fetched externally', async ({
    page,
  }) => {
    // NFR-3 applies to the page, not only to the API. A stylesheet linking a
    // font CDN would break the interface on the firewall Marcus Williams
    // describes, and would do it silently.
    // Anything not on the loopback address the preview server binds to. Not
    // compared against `page.url()`, which is still about:blank when the first
    // request is made and would count the page's own document as external.
    const external: string[] = []
    page.on('request', (request) => {
      const { hostname } = new URL(request.url())
      if (hostname !== '127.0.0.1' && hostname !== 'localhost') external.push(request.url())
    })
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    expect(external).toEqual([])

    const family = await page
      .locator('h1')
      .evaluate((element) => getComputedStyle(element).fontFamily)
    expect(family).toContain('Inter Variable')
  })

  test('the chosen photograph is previewed in the scan frame, and it is decoration', async ({
    page,
  }) => {
    await page.goto('/')
    await page.getByLabel('Label image').setInputFiles({
      name: 'stones-throw.png',
      // A one-pixel PNG, so the element has something real to load.
      mimeType: 'image/png',
      buffer: Buffer.from(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
        'base64',
      ),
    })

    // The preview carries the file's name as its alternative text, and the
    // frame's corner brackets are decoration with no accessible name of their
    // own.
    const preview = page.getByAltText('Preview of stones-throw.png')
    await expect(preview).toBeVisible()
    await expect(preview).toHaveJSProperty('naturalWidth', 1)

    const found = await violations(page)
    expect(report(found)).toBe('')
  })

  test('the primary task is on the landing page with no navigation (NFR-4)', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByLabel('Label image')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Check this label' })).toBeVisible()
  })

  test('a second and third photo of the same label are reachable by keyboard', async ({ page }) => {
    await page.goto('/')
    const panel = page.locator('#panel-single')

    await panel.getByRole('button', { name: 'Add another photo of this label' }).click()
    await expect(panel.getByLabel('Label image, photo 2')).toBeVisible()
    await expect(panel.getByRole('button', { name: 'Remove photo 2' })).toBeVisible()

    await panel.getByRole('button', { name: 'Add another photo of this label' }).click()
    await expect(panel.getByLabel('Label image, photo 3')).toBeVisible()
    // The cap is enforced by withdrawing the control, so an agent never reaches
    // the API's refusal (NFR-4, ADR 0007).
    await expect(
      panel.getByRole('button', { name: 'Add another photo of this label' }),
    ).toHaveCount(0)

    // Removing a slot has to leave focus somewhere usable, which is what a
    // keyboard user loses if the removed button simply disappears.
    await panel.getByRole('button', { name: 'Remove photo 3' }).click()
    await expect(
      panel.getByRole('button', { name: 'Add another photo of this label' }),
    ).toBeFocused()
  })

  test('the collapsed disclosure is axe-clean, and opening it stays axe-clean', async ({
    page,
  }) => {
    await page.goto('/')
    const panel = page.locator('#panel-single')
    const disclosure = panel.getByRole('button', { name: 'Or type the application values' })

    // Collapsed is the state the page loads in, so it is the state most
    // reviewers will scan (US-24, NFR-4).
    await expect(disclosure).toHaveAttribute('aria-expanded', 'false')
    await expect(panel.getByLabel('Brand name', { exact: true })).toBeHidden()
    expect(report(await violations(page))).toBe('')

    await disclosure.click()
    await expect(disclosure).toHaveAttribute('aria-expanded', 'true')
    await expect(panel.getByLabel('Brand name', { exact: true })).toBeVisible()
    expect(report(await violations(page))).toBe('')
  })

  test('a document with gaps opens the typed fields and announces why (US-24)', async ({
    page,
  }) => {
    // The honest shape of TTB F 5100.31 (04/2023): a brand name, and no class
    // or type, alcohol content or net contents boxes at all (A-17). Gaps are
    // the normal outcome on the form proper, not an error.
    await page.route('**/api/read-application', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(FORM_WITH_GAPS),
      })
    })
    await page.goto('/')
    const panel = page.locator('#panel-single')

    await expect(
      panel.getByRole('button', { name: 'Or type the application values' }),
    ).toHaveAttribute('aria-expanded', 'false')

    await panel.getByLabel('Label application', { exact: true }).setInputFiles({
      name: 'application.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from([37, 80, 68, 70]),
    })

    await expect(
      panel.getByRole('button', { name: 'Or type the application values' }),
    ).toHaveAttribute('aria-expanded', 'true')
    // The parsed value is filled; the gaps are empty and waiting.
    await expect(panel.getByLabel('Brand name', { exact: true })).toHaveValue("STONE'S THROW")
    await expect(panel.getByLabel('Alcohol content', { exact: true })).toHaveValue('')
    // And the expansion is announced, rather than only being visible.
    await expect(panel.getByLabel('Application values')).toContainText(
      'The application values are open below',
    )

    expect(report(await violations(page))).toBe('')
  })

  test('the COLA document upload is labelled, announced and axe-clean', async ({ page }) => {
    await page.route('**/api/read-application', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(PARSED_APPLICATION),
      })
    })
    await page.goto('/')
    const panel = page.locator('#panel-single')

    await panel.getByLabel('Label application', { exact: true }).setInputFiles({
      name: 'application.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from([37, 80, 68, 70]),
    })

    // PARSED_APPLICATION leaves the beverage type unread, which is a gap, so
    // the typed fields open on their own (US-24, expansion case 2).
    await expect(
      panel.getByRole('button', { name: 'Or type the application values' }),
    ).toHaveAttribute('aria-expanded', 'true')

    // The parsed values reach the same fields an agent would have typed into,
    // and every one of them says where it came from (FR-11, ADR 0008).
    await expect(panel.getByLabel('Brand name', { exact: true })).toHaveValue("STONE'S THROW")
    await expect(
      panel.getByText('Read from the application form. Change it if it is wrong.').first(),
    ).toBeVisible()
    await expect(panel.getByRole('button', { name: 'Remove this application form' })).toBeVisible()

    const found = await violations(page)
    expect(report(found)).toBe('')
  })

  test('the axe scan covers a result built from two photos', async ({ page }) => {
    await page.route('**/api/verify', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(RESULT),
      })
    })
    await page.goto('/')
    await page.getByLabel('Label image').setInputFiles({
      name: 'front.png',
      mimeType: 'image/png',
      buffer: Buffer.from([137, 80, 78, 71]),
    })
    await page.getByRole('button', { name: 'Check this label' }).click()

    await expect(page.getByRole('region', { name: 'Your 2 photos' })).toBeVisible()
    await expect(page.getByText(/we turned it 90 degrees to read it/i)).toBeVisible()
    await expect(page.getByText(/read from photo 2/i).first()).toBeVisible()
  })
})

const WARNING_NOTE =
  'Bold type was not checked. 27 CFR 16.22(a)(2) also requires the prefix to be in bold, and this prototype does not check typeface.'

const RESULT = {
  fields: [
    {
      name: 'brand_name',
      display_name: 'Brand name',
      found_on_label: true,
      label_value: "STONE'S THROW",
      application_value: "Stone's Throw",
      score: 100,
      outcome: 'match',
      reason: 'Scored 100, at or above the match threshold of 95.',
      source_photo: 1,
      application_value_source: 'typed',
    },
    {
      name: 'class_type',
      display_name: 'Class or type designation',
      found_on_label: true,
      label_value: 'Kentucky Straight Bourbon Whiskey',
      application_value: 'Kentucky Straight Bourbon',
      score: 88,
      outcome: 'needs_review',
      reason: 'Scored 88, between the review threshold of 80 and the match threshold of 95.',
      source_photo: 1,
      application_value_source: 'typed',
    },
    {
      name: 'alcohol_content',
      display_name: 'Alcohol content',
      found_on_label: true,
      label_value: '45% Alc./Vol. (90 Proof)',
      application_value: '40',
      score: null,
      outcome: 'mismatch',
      reason: 'The label states 45 percent and the application states 40 percent.',
      source_photo: 2,
      application_value_source: 'typed',
    },
    {
      name: 'net_contents',
      display_name: 'Net contents',
      found_on_label: false,
      label_value: null,
      application_value: '750 mL',
      score: null,
      outcome: 'not_compared',
      reason: 'Net contents were not found on the label, so nothing was compared.',
      source_photo: null,
      application_value_source: 'typed',
    },
    {
      name: 'government_warning',
      display_name: 'Government warning statement',
      found_on_label: true,
      label_value: 'Government Warning: (1) According to the Surgeon General...',
      application_value: 'GOVERNMENT WARNING: (1) According to the Surgeon General...',
      score: null,
      outcome: 'mismatch',
      reason: `The prefix is not in capital letters. ${WARNING_NOTE}`,
      source_photo: 2,
      application_value_source: 'typed',
    },
  ],
  warning_detail: {
    statement_found: true,
    prefix_as_printed: 'Government Warning:',
    prefix_is_capitalized: false,
    body_matches_regulation: true,
    bold_type_checked: false,
    bold_type_note: WARNING_NOTE,
  },
  photos: [
    {
      index: 1,
      orientation: {
        exif_transposed: false,
        rotation_degrees: 90,
        method: 'osd',
        confidence: 13.4,
      },
      ocr_confidence: 94.1,
      text_found: true,
      error: null,
    },
    {
      index: 2,
      orientation: {
        exif_transposed: true,
        rotation_degrees: 0,
        method: 'osd',
        confidence: 12.8,
      },
      ocr_confidence: 91.7,
      text_found: true,
      error: null,
    },
  ],
  ocr_confidence: 94.1,
  elapsed_ms: 540,
  ocr_ms: 530,
  external_call_made: false,
  application_document: null,
}

/** What POST /api/read-application returns for a registry printout (FR-11). */
/**
 * A read of TTB F 5100.31 (04/2023) itself, which carries the brand name and
 * has no box for the class or type, the alcohol content or the net contents
 * (A-17). This is the gap case US-24's second expansion rule exists for.
 */
const FORM_WITH_GAPS = {
  extraction_path: 'form_fields',
  pages_read: 1,
  fields: [
    {
      name: 'brand_name',
      display_name: 'Brand name',
      value: "STONE'S THROW",
      found_on_document: true,
    },
    {
      name: 'class_type',
      display_name: 'Class or type designation',
      value: null,
      found_on_document: false,
    },
    {
      name: 'alcohol_content',
      display_name: 'Alcohol content',
      value: null,
      found_on_document: false,
    },
    {
      name: 'net_contents',
      display_name: 'Net contents',
      value: null,
      found_on_document: false,
    },
    {
      name: 'beverage_type',
      display_name: 'Beverage type',
      value: 'distilled spirits',
      found_on_document: true,
    },
  ],
  fanciful_name: 'Small Batch Reserve',
  class_type_code: null,
  notes: [
    'The class or type designation is not an item on TTB F 5100.31 (04/2023).',
    'The alcohol content is not an item on TTB F 5100.31 (04/2023).',
    'The net contents is an item on TTB F 5100.31 (04/2023) only when it is blown, branded or embossed on the container.',
  ],
}

const PARSED_APPLICATION = {
  extraction_path: 'embedded_text',
  pages_read: 1,
  fields: [
    {
      name: 'brand_name',
      display_name: 'Brand name',
      value: "STONE'S THROW",
      found_on_document: true,
    },
    {
      name: 'class_type',
      display_name: 'Class or type designation',
      value: 'KENTUCKY STRAIGHT BOURBON WHISKEY',
      found_on_document: true,
    },
    {
      name: 'alcohol_content',
      display_name: 'Alcohol content',
      value: '45% ALC/VOL',
      found_on_document: true,
    },
    {
      name: 'net_contents',
      display_name: 'Net contents',
      value: '750 ML',
      found_on_document: true,
    },
    {
      name: 'beverage_type',
      display_name: 'Beverage type',
      value: null,
      found_on_document: false,
    },
  ],
  fanciful_name: 'Small Batch Reserve',
  class_type_code: '141',
  notes: [
    "The type of product is item 5 on TTB F 5100.31 (04/2023), three checkboxes. A ticked box cannot be read from a document's text, and this document did not name one type on its own. Choose it yourself.",
  ],
}
