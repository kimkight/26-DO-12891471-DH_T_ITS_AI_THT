/**
 * The interface does not claim a capability it does not have (US-27, NFR-4).
 *
 * **The application has no camera.** Nothing is pointed at anything. An agent
 * chooses a file and uploads it. The heading read "Point. Upload. Check.",
 * inherited from a pattern written for a phone, and the first word described
 * something this tool cannot do. Copy that promises a camera to an agent who is
 * holding a mouse is exactly the small dishonesty Dave Morrison has learned to
 * distrust, and it is not made harmless by being decoration.
 *
 * **The rule, and it is narrower than "remove the word photo".** A word that
 * implies the tool takes the picture goes. A word that describes a file the
 * agent already has stays: "photo", "photograph" and "scan" are all correct as
 * nouns for something an agent is uploading, and replacing them would make the
 * copy vaguer without making it truer.
 *
 * The sweep is asserted against the rendered interface rather than against the
 * source, because what matters is what an agent reads.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from '../App'
import { SIDES } from '../lib/uploadAnnouncement'
import { plainMessage } from '../lib/plainLanguage'

/** Everything the landing page renders, as one string. */
function landingText(): string {
  const { container } = render(<App />)
  return container.textContent ?? ''
}

describe('the heading names things the interface actually performs', () => {
  it('no longer tells the agent to point anything at anything', () => {
    render(<App />)
    expect(screen.queryByText('Point. Upload. Check.')).not.toBeInTheDocument()
  })

  it('reads as three verbs this application does perform', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Upload. Read. Check.' })).toBeInTheDocument()
  })

  it('the kicker above it stops calling an upload a scan', () => {
    render(<App />)
    expect(screen.getByText('Label check')).toBeInTheDocument()
    expect(screen.queryByText('Label scanning')).not.toBeInTheDocument()
  })
})

describe('no string on the landing page implies the tool captures anything', () => {
  /*
   * Words that only ever appear when something is being pointed at a subject.
   * "Photograph" and "photo" are deliberately absent from this list: they are
   * correct as nouns for a file, and the interface still uses them that way.
   */
  const CAPTURE_WORDS = [
    'Point.',
    'point your',
    'camera',
    'viewfinder',
    'take a photo',
    'take a picture',
    'snap',
    'scan the label',
    'scanning',
  ]

  it.each(CAPTURE_WORDS)('does not say "%s"', (word) => {
    expect(landingText().toLowerCase()).not.toContain(word.toLowerCase())
  })
})

describe('the upload copy describes files rather than photography', () => {
  it('asks for an image of the label, which covers artwork as well as a photo', () => {
    const text = landingText()
    expect(text).toContain('Upload the label application, an image of the label, or both')
    expect(text).not.toContain('a photo of the label, or both')
  })

  it('says PDFs and images, because a label export is not a photo', () => {
    expect(landingText()).toContain('PDFs and images, one file or several')
  })

  it('names a file classified as the label side without calling it a picture taken', () => {
    expect(SIDES.label_image).toBe('Label image')
  })

  it('asks for a clearer image rather than presuming the source was a photo', () => {
    expect(plainMessage('unreadable_image')).toBe(
      "We couldn't read this label. Try a clearer image.",
    )
  })
})

describe('what the sweep deliberately keeps', () => {
  /*
   * These describe a file the agent is holding, which is what the word means
   * there. Asserted so that a later sweep does not remove them for looking like
   * the ones that went, and so the distinction is written down somewhere a
   * reader will find it.
   */
  it('still tells an agent whose photographs were all unreadable to retake them', () => {
    expect(plainMessage('all_photos_unreadable')).toContain('Try clearer photos, in better light')
  })

  it('still accepts a photo or a scan of the application form, and says so', () => {
    expect(plainMessage('unsupported_application_document')).toContain(
      'a photo or scan of the form',
    )
  })
})
