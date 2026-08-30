/**
 * One outcome, as text and shape and colour (FR-10, NFR-5).
 *
 * The three carriers are independent on purpose. The word is readable with no
 * styles at all, the shape differs per outcome rather than being one shape
 * recoloured, and the colour is the last of the three to arrive. NFR-5's first
 * criterion is that outcomes are conveyed by text and shape, not by colour
 * alone; this component is where that is either true or false.
 *
 * The icon is `aria-hidden` because the word beside it already says the same
 * thing. Labelling both would make a screen reader say "match match".
 */
import { presentation } from '../lib/outcomes'
import type { Glyph } from '../lib/outcomes'
import type { Outcome } from '../types'

function Icon({ glyph }: { glyph: Glyph }) {
  const shapes: Record<Glyph, React.ReactNode> = {
    check: <path d="M3 8.5 6.5 12 13 4" />,
    triangle: <path d="M8 2.5 14.5 13.5h-13Z M8 6.5v3 M8 11.4v.1" />,
    cross: <path d="M4 4l8 8 M12 4l-8 8" />,
    dash: <path d="M3.5 8h9" />,
    // A picture in a frame: the one shape that says "this came off the
    // artwork" rather than saying how a comparison went (FR-14, ADR 0013).
    artwork: <path d="M2.5 3.5h11v9h-11z M2.5 11 6 7.5l2.5 2.5L10.5 8l3 3 M5.5 6.4v.01" />,
  }
  return (
    <svg
      className="badge__icon"
      viewBox="0 0 16 16"
      width="16"
      height="16"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {shapes[glyph]}
    </svg>
  )
}

export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  const { label, glyph, tone } = presentation(outcome)
  return (
    <span className={`badge badge--${tone}`} data-outcome={outcome}>
      <Icon glyph={glyph} />
      <span className="badge__label">{label}</span>
    </span>
  )
}
