/**
 * Where each application value came from, in the agent's words (ADR 0010).
 *
 * The API reports a precedence: typed by the agent, then the document's own
 * text, then label artwork embedded in that document, then absent. An agent
 * looking at a prefilled field is entitled to know which of those they are
 * looking at, because the three are not equally reliable. A value read out of a
 * text layer cannot be misread; a value recognized off a picture can.
 *
 * Kept here rather than inline in a component because these are decisions about
 * wording, they are used from more than one place, and they are worth asserting
 * in a test without rendering anything.
 */
import type { ApplicationSource, DocumentValueSource } from '../types'

/** The short chip text for each source. Four sources, four labels. */
const SOURCE_LABELS: Record<ApplicationSource, string> = {
  typed: 'You typed this',
  parsed_from_form: 'Application form',
  parsed_from_artwork: 'Label artwork in the application',
  absent: 'Not supplied',
}

/**
 * How the document reports a source, mapped onto the same four.
 *
 * The document distinguishes an AcroForm field from a text layer; an agent has
 * no use for that distinction, because both are text the file itself states and
 * neither went through a recognition step. What an agent does have a use for is
 * text against artwork.
 */
const DOCUMENT_SOURCES: Record<DocumentValueSource, ApplicationSource> = {
  form_fields: 'parsed_from_form',
  embedded_text: 'parsed_from_form',
  embedded_artwork: 'parsed_from_artwork',
  absent: 'absent',
}

export function sourceChipLabel(source: ApplicationSource): string {
  return SOURCE_LABELS[source]
}

/**
 * Defaulted rather than indexed blindly: a response from a server that predates
 * ADR 0010 carries no per-value source, and a value that came off a document
 * with no source recorded is still a value that came off a document. Losing the
 * mark on it would tell the agent they typed something they did not.
 */
export function documentSource(source: DocumentValueSource | undefined): ApplicationSource {
  return (source && DOCUMENT_SOURCES[source]) || 'parsed_from_form'
}

/**
 * The mark on a filled field, saying where its value came from.
 *
 * Kept in the wording it has had since FR-11 ("Read from the application form.
 * Change it if it is wrong.") because the second sentence is the working half:
 * an agent who cannot tell whether they are allowed to edit a filled field will
 * not edit it. What is added is the artwork case, which is the one an agent
 * should look at hardest.
 */
const FIELD_MARKS: Record<ApplicationSource, string | null> = {
  typed: null,
  parsed_from_form: 'Read from the application form. Change it if it is wrong.',
  parsed_from_artwork:
    'Read from the label artwork inside the application. Change it if it is wrong.',
  absent: null,
}

export function fieldSourceMark(source: ApplicationSource): string | null {
  return FIELD_MARKS[source]
}

/**
 * The one line that says a value was recognized off a picture rather than read
 * out of the file, and what to do about it.
 *
 * Only the artwork source gets one. The other three need no caveat: a typed
 * value is the agent's own, a text-layer value is what the file says, and an
 * absent value is already reported as absent.
 */
export function sourceCaveat(source: ApplicationSource): string | null {
  return source === 'parsed_from_artwork'
    ? 'Read from the picture of the label inside the application, not from its text. Check it.'
    : null
}

/**
 * The single line the result panel shows when the label being checked came out
 * of the application document rather than out of a photograph (ADR 0010).
 *
 * One short line, deliberately. The full statement is in the API's
 * `self_consistency_note` and in ADR 0010; what an agent needs on screen is
 * what was checked against what, and the fact that it is not the bottle.
 */
export const ARTWORK_LABEL_LINE =
  'The label checked here is the artwork inside the application document, not a photo of a bottle. ' +
  'This checks that the filed artwork carries the required elements and agrees with the form. ' +
  'Checking the physical bottle needs a photo of that bottle.'

/**
 * What the artwork-derived row says about itself, on the row (FR-14, ADR 0013).
 *
 * **On the row rather than in a footnote**, which is the requirement and not a
 * presentation preference. An agent scanning five results has to be able to see
 * why one of them is different from the others without reading anything else on
 * the page; a caveat at the bottom of the panel is read by the people who
 * already understood, and missed by everyone else.
 *
 * The parenthetical is the whole of the point. "Label artwork" alone is already
 * on the row for any value that came off a picture, including the ones checked
 * against an independent photograph. What makes this row different is that the
 * artwork is *also* the label side, and the phrase says so.
 */
export const ARTWORK_DERIVED_SOURCE = 'Label artwork (same source as the label)'

/**
 * The one line under it, saying what that means for the agent.
 *
 * It supersedes `sourceCaveat` on this row rather than joining it. The generic
 * artwork caveat warns that a value recognized off a picture can be misread,
 * which is true here too and is the smaller of the two problems; two notes on
 * one card is noise, and the larger problem is the one worth the line.
 */
export const ARTWORK_DERIVED_CAVEAT =
  'Both sides of this row are one reading of one picture, so they could not have disagreed. ' +
  'It shows the artwork carries this value. It shows nothing about whether the applicant declared the same one.'
