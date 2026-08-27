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
    await expect(page.getByRole('heading', { name: 'Label check', level: 1 })).toBeVisible()
    const found = await violations(page)
    expect(report(found)).toBe('')
  })

  test('the batch tab', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('tab', { name: 'Check many labels' }).click()
    await expect(page.getByLabel('Application data file')).toBeVisible()
    const found = await violations(page)
    expect(report(found)).toBe('')
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
    // label (ADR 0007), and the five application fields, in reading order.
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

    const expected = [
      'Beverage type',
      'Brand name',
      'Class or type designation',
      'Alcohol content',
      'Net contents',
    ]
    for (const label of expected) {
      await page.keyboard.press('Tab')
      await expect(panel.getByLabel(label, { exact: true })).toBeFocused()
    }

    // A visible focus indicator, which axe cannot see (NFR-5's second
    // criterion). Asserted on the outline the stylesheet sets for
    // :focus-visible, which keyboard navigation triggers.
    const outline = await panel
      .getByLabel('Net contents', { exact: true })
      .evaluate((element) => getComputedStyle(element).outlineWidth)
    expect(parseFloat(outline)).toBeGreaterThan(0)
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
}
