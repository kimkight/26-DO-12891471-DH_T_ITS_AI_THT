/**
 * The small presentational pieces the restyle introduced, in one place.
 *
 * A kicker, a status chip, a rounded icon tile, and the frame that previews a
 * chosen file. They are here rather than inlined because each appears in more
 * than one view, and a chip whose padding differs by a pixel between two panels
 * is the kind of thing nobody fixes later.
 *
 * **None of them carries meaning on its own.** Every glyph is `aria-hidden`,
 * because in every case the text beside it says the same thing; NFR-5's rule
 * that outcomes are conveyed by text and shape rather than by colour applies to
 * decoration as much as to results, and the cheapest way to keep it is to make
 * the decoration say nothing.
 */
import { useEffect, useRef } from 'react'
import { canPreview, previewPlaceholder } from '../lib/preview'

/** The glyphs the kickers and tiles use. Geometric, and none of them a mark. */
type GlyphName = 'label' | 'document' | 'stack' | 'check'

const PATHS: Record<GlyphName, React.ReactNode> = {
  // A bottle label: a rectangle with two lines of type on it.
  //
  // **It replaced a viewfinder**, four corner brackets, which was the same
  // shape the preview frame used to draw at full size. Corner brackets mean one
  // thing: align the subject here and the device will capture it. This
  // application has no camera and captures nothing, and an icon that says
  // otherwise is the same promise the old "Point." heading made (US-27).
  label: (
    <>
      <path d="M2.5 4.5h15a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-15a1 1 0 0 1-1-1v-9a1 1 0 0 1 1-1Z" />
      <path d="M5 8.5h10M5 11.5h6" />
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

// `CAN_PREVIEW` and the per-type decision live in lib/preview.ts.

/**
 * The chosen file, previewed so an agent can see what they picked.
 *
 * **The panel stays; the viewfinder brackets do not** (US-27). The reason the
 * preview exists is good and unchanged: before it, an agent who chose a file
 * got the filename back and nothing else, so a picture of the wrong bottle
 * looked exactly like a picture of the right one until the results came back.
 *
 * The four gold corner brackets were a different thing, and they fail the same
 * test the old "Point. Upload. Check." heading failed. Corner brackets are the
 * universal signifier of a live camera viewfinder: they mean align the subject
 * here and the device will capture it. Nothing here is being aligned and
 * nothing is being captured. By the time this renders the file has been chosen,
 * uploaded and read. The brackets told an agent the tool was looking through a
 * lens at something, which is not true, and a small untruth in the furniture is
 * exactly what a sceptical user learns to distrust a tool over.
 *
 * So the frame, the image and the caption stay, because they do the job; the
 * brackets are gone, and the class names say `preview` rather than `scan`, so
 * the code stops calling it a scan too.
 *
 * The object URL is written straight onto the element and revoked on cleanup,
 * rather than being held in state. That is what an effect is for: synchronising
 * React with an external system, here the browser's blob registry, without a
 * render pass whose only purpose is to carry a string that the DOM node could
 * have held itself.
 */
export function FilePreview({ file }: { file: File }) {
  const imageRef = useRef<HTMLImageElement>(null)
  const drawable = canPreview(file)

  useEffect(() => {
    const node = imageRef.current
    if (!node || !drawable) return
    const url = URL.createObjectURL(file)
    node.src = url
    return () => {
      node.removeAttribute('src')
      URL.revokeObjectURL(url)
    }
  }, [file, drawable])

  return (
    <div className="preview">
      <div className="preview__viewport">
        {drawable ? (
          <img className="preview__image" ref={imageRef} alt={`Preview of ${file.name}`} />
        ) : (
          <p className="preview__fallback" data-testid="preview-placeholder">
            {previewPlaceholder(file)}
          </p>
        )}
      </div>
      <p className="preview__caption">{file.name}</p>
    </div>
  )
}
