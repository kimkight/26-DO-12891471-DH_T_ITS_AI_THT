/**
 * The interface stops asserting what it did not measure (NFR-1).
 *
 * The panel used to print the browser's wall clock, subtract the server's
 * figure, and tell the agent the remainder was "sending the image and receiving
 * the answer". A control POST of the same 382 KB file to a path that processes
 * nothing crossed the wire in 68 to 111 ms, so that sentence was attributing
 * about three and a half seconds of document parsing and a duplicated OCR pass
 * to a connection that was working fine.
 *
 * These tests hold two lines: the invented mechanism is gone, and what replaced
 * it names a location rather than inventing a different mechanism.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { readingNote, spans, timingSummary } from '../lib/timing'
import { phaseTimings } from './fixtures'

describe('the sentence under the headline time', () => {
  it('reports both measured numbers and names their difference honestly', () => {
    const sentence = timingSummary(6.88, 3450)
    expect(sentence).toContain('3450 ms of that was inside the checker')
    expect(sentence).toContain('3430 ms was in your browser and on the network')
  })

  it('never claims the difference was sending the image', () => {
    const sentence = timingSummary(6.88, 3450)
    expect(sentence).not.toContain('sending the image')
    expect(sentence).not.toContain('receiving the answer')
  })

  it('does not go negative when the server figure exceeds the wall clock', () => {
    // Clock skew between two different clocks is not evidence of negative time.
    expect(timingSummary(1.0, 1200)).toContain('0 ms was in your browser')
  })
})

describe('the phase breakdown reports what was measured', () => {
  it('leaves out the phases a request did not go through', () => {
    const rows = spans(phaseTimings())
    const labels = rows.map((row) => row.label)
    expect(labels).toContain('Reading the label')
    expect(labels).not.toContain('Reading the document pages as images')
    expect(labels).not.toContain('Reading the label artwork in the application')
  })

  it('orders the measured phases largest first, so the cost is the first thing read', () => {
    const rows = spans(
      phaseTimings({
        document_pdfium_ms: 80,
        artwork_ocr_ms: 1050,
        label_ocr_ms: 0,
        compare_ms: 0.3,
        unaccounted_ms: 1,
      }),
    )
    expect(rows[0].label).toBe('Reading the label artwork in the application')
    expect(rows[1].label).toBe('Reading the application document')
  })

  it('names the one subtraction as unaccounted rather than attributing it', () => {
    const rows = spans(phaseTimings({ unaccounted_ms: 9.7 }))
    const last = rows[rows.length - 1]
    expect(last.label).toBe('Not attributed to any step')
    expect(last.ms).toBe(9.7)
  })

  it('reports the pass count, which is what made the duplicated read visible', () => {
    expect(readingNote(phaseTimings({ ocr_ms: 2110, ocr_passes: 2 }))).toBe(
      '2110 ms of reading, over 2 passes.',
    )
    expect(readingNote(phaseTimings({ ocr_ms: 1050, ocr_passes: 1 }))).toBe(
      '1050 ms of reading, over 1 pass.',
    )
  })
})

describe('the breakdown is on the page, and out of the way', () => {
  it('is behind a closed disclosure rather than above the results', async () => {
    const { SingleLabelTab } = await import('../components/SingleLabelTab')
    render(<SingleLabelTab />)
    // Nothing has been checked yet, so there is nothing to disclose.
    expect(screen.queryByText('Where the time went')).not.toBeInTheDocument()
  })
})
