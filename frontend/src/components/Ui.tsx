/**
 * The small presentational pieces the restyle introduced, in one place.
 *
 * A kicker, a status chip, a rounded icon tile, and the scan frame that
 * previews a chosen photograph. They are here rather than inlined because each
 * appears in more than one view, and a chip whose padding differs by a pixel
 * between two panels is the kind of thing nobody fixes later.
 *
 * **None of them carries meaning on its own.** Every glyph is `aria-hidden`,
 * because in every case the text beside it says the same thing; NFR-5's rule
 * that outcomes are conveyed by text and shape rather than by colour applies to
 * decoration as much as to results, and the cheapest way to keep it is to make
 * the decoration say nothing.
 */
import { useEffect, useRef } from 'react'

/** The glyphs the kickers and tiles use. Geometric, and none of them a mark. */
type GlyphName = 'scan' | 'document' | 'stack' | 'check'

const PATHS: Record<GlyphName, React.ReactNode> = {
  // A viewfinder: four corner brackets, which is the same shape the scan frame
  // draws in CSS at full size.
  scan: (
    <>
      <path d="M2.5 6V3.5A1 1 0 0 1 3.5 2.5H6" />
      <path d="M14 2.5h2.5a1 1 0 0 1 1 1V6" />
      <path d="M17.5 14v2.5a1 1 0 0 1-1 1H14" />
      <path d="M6 17.5H3.5a1 1 0 0 1-1-1V14" />
      <path d="M5.5 10h9" />
    </>
  ),
  document: (
    <>
      <path d="M4.5 2.5h7l4 4v11a1 1 0 0 1-1 1h-10a1 1 0 0 1-1-1v-14a1 1 0 0 1 1-1Z" />
      <path d="M11.5 2.5v4h4" />
      <path d="M7 11h6M7 14h4" />
    </>
  ),
  stack: (
    <>
      <path d="M10 2.5 17.5 6.5 10 10.5 2.5 6.5 10 2.5Z" />
      <path d="M2.5 10.5 10 14.5l7.5-4" />
      <path d="M2.5 14 10 18l7.5-4" />
    </>
  ),
  check: <path d="M3.5 10.5 8 15l8.5-10" />,
}

function Glyph({ glyph }: { glyph: GlyphName }) {
  return (
    <svg
      className="kicker__icon"
      viewBox="0 0 20 20"
      width="14"
      height="14"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[glyph]}
    </svg>
  )
}

/**
 * A small-caps, letter-spaced label with a leading icon, above a card title.
 *
 * It says what kind of thing the card is; the title under it says what the card
 * does, as a short declarative sentence. Rendered as a `<p>` rather than as a
 * heading: it is not a level in the document outline, and making it one would
 * put a second entry into a screen reader's heading list for every card.
 */
export function Kicker({
  children,
  glyph,
  tone = 'gold',
}: {
  children: React.ReactNode
  glyph: GlyphName
  tone?: 'gold' | 'navy'
}) {
  return (
    <p className={`kicker${tone === 'navy' ? ' kicker--navy' : ''}`}>
      <Glyph glyph={glyph} />
      {children}
    </p>
  )
}

/**
 * A small rounded chip for a count or a state.
 *
 * Text first, always. A chip that said something only through its colour would
 * fail NFR-5, so every one of these reads correctly with the colour removed.
 */
export function Chip({
  children,
  tone = 'neutral',
  dot = false,
}: {
  children: React.ReactNode
  tone?: 'neutral' | 'navy' | 'gold'
  dot?: boolean
}) {
  return (
    <span className={`chip${tone === 'neutral' ? '' : ` chip--${tone}`}`}>
      {dot ? <span className="chip__dot" aria-hidden="true" /> : null}
      {children}
    </span>
  )
}

/**
 * A rounded-square icon tile heading a feature area, with its heading beside it.
 *
 * The tile is decoration. The heading it sits next to carries the meaning, and
 * the glyph is hidden from assistive technology for that reason.
 */
export function TileHeading({
  glyph,
  tone = 'navy',
  children,
}: {
  glyph: GlyphName
  tone?: 'navy' | 'gold'
  children: React.ReactNode
}) {
  return (
    <div className="tile-heading">
      <span className={`tile${tone === 'gold' ? ' tile--gold' : ''}`} aria-hidden="true">
        <svg
          viewBox="0 0 20 20"
          width="20"
          height="20"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
          focusable="false"
        >
          {PATHS[glyph]}
        </svg>
      </span>
      <div className="tile-heading__body">{children}</div>
    </div>
  )
}

/**
 * Whether this environment can make an object URL for a chosen file.
 *
 * A constant rather than a per-render check: it is a property of the platform,
 * not of the file. jsdom does not implement `createObjectURL`, and the unit
 * tests render this tree with real `File` objects, so without this the preview
 * would throw in every one of them. In a browser it is always true, and the
 * Chromium accessibility run is what exercises the real path.
 */
const CAN_PREVIEW = typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function'

/**
 * The chosen photograph, inside a scan frame with gold corner brackets.
 *
 * It exists for a reason beyond looking like a scanner. Before it, an agent who
 * chose a file got the filename back and nothing else, so a photograph of the
 * wrong bottle looked exactly like a photograph of the right one until the
 * results came back. The brackets are drawn in CSS and are decoration; the
 * image carries an alt attribute naming the file it is showing.
 *
 * The object URL is written straight onto the element and revoked on cleanup,
 * rather than being held in state. That is what an effect is for: synchronising
 * React with an external system, here the browser's blob registry, without a
 * render pass whose only purpose is to carry a string that the DOM node could
 * have held itself.
 */
export function ScanFrame({ file }: { file: File }) {
  const imageRef = useRef<HTMLImageElement>(null)

  useEffect(() => {
    const node = imageRef.current
    if (!node) return
    const url = URL.createObjectURL(file)
    node.src = url
    return () => {
      node.removeAttribute('src')
      URL.revokeObjectURL(url)
    }
  }, [file])

  return (
    <div className="scan">
      <div className="scan__viewport">
        {CAN_PREVIEW ? (
          <img className="scan__image" ref={imageRef} alt={`Preview of ${file.name}`} />
        ) : (
          <p className="scan__fallback">Preview unavailable in this browser.</p>
        )}
        <span className="scan__bracket scan__bracket--tl" aria-hidden="true" />
        <span className="scan__bracket scan__bracket--tr" aria-hidden="true" />
        <span className="scan__bracket scan__bracket--bl" aria-hidden="true" />
        <span className="scan__bracket scan__bracket--br" aria-hidden="true" />
      </div>
      <p className="scan__caption">{file.name}</p>
    </div>
  )
}
