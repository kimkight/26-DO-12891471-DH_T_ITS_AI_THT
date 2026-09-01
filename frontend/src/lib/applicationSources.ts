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

/** The short chip text for each source. One label per source, no sharing. */
const SOURCE_LABELS: Record<ApplicationSource, string> = {
  typed: 'You typed this',
  parsed_from_form: 'Application form',
  parsed_from_artwork: 'Label artwork in the application',
  read_from_tick: 'Ticked box on the form',
  absent: 'Not supplied',
}

/**
 * How the document reports a source, mapped onto the same four.
 *
 * The document distinguishes an AcroForm field from a text layer; an agent has
 * no use for that distinction, because both are text the file itself states and
 * neither went through a recognition step. What an agent does have a use for is
 * text against a picture, and there are two kinds of picture: the label artwork
 * inside the application, and item 5's own check boxes on the form's page
 * (ADR 0016). Those two are kept apart because they are read for different
 * fields and an agent checking one is not checking the other.
 */
const DOCUMENT_SOURCES: Record<DocumentValueSource, ApplicationSource> = {
  form_fields: 'parsed_from_form',
  embedded_text: 'parsed_from_form',
  embedded_artwork: 'parsed_from_artwork',
  product_type_box: 'read_from_tick',
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
 * Kept in the wording it has had since FR-11 because the second half is the
 * working half: an agent who cannot tell whether they are allowed to edit a
 * filled field will not edit it. What is added is the artwork case, which is
 * the one an agent should look at hardest.
 *
 * One sentence rather than two since 2026-09-01 (US-28), joined by a semicolon.
 * Nothing is lost by that and it is not a cosmetic change: the check screen's
 * rule is one sentence per paragraph, and a mark that broke it would be the
 * first exception, after which there would be a second.
 */
const FIELD_MARKS: Record<ApplicationSource, string | null> = {
  typed: null,
  parsed_from_form: 'Read from the application form; change it if it is wrong.',
  parsed_from_artwork:
    'Read from the label artwork inside the application; change it if it is wrong.',
  read_from_tick: 'Read from the ticked box in item 5; change it if it is wrong.',
  absent: null,
}

export function fieldSourceMark(source: ApplicationSource): string | null {
  return FIELD_MARKS[source]
}

/*
 * `sourceCaveat` was here, and it said in a sentence what the chip beside every
 * affected value already says in four words: this one came off a picture. It
 * appeared on each read value in the upload summary and again on each result
 * row, which made it the third and fourth telling of a thing said once in the
 * upload card. Removed 2026-08-31; the upload card's own line is the one that
 * survives, because that is where the values are first shown.
 */

/**
 * The single line the result panel shows when the label being checked came out
 * of the application document rather than out of a photograph (ADR 0010).
 *
 * One short line, deliberately, and shorter again since 2026-08-31. The full
 * statement is in the API's `self_consistency_note` and in ADR 0010; the two
 * sentences that followed this one restated what the reader can work out from
 * it, and the upload card had already said the same thing before the check ran.
 * What an agent needs on screen is what was checked against what.
 */
export const ARTWORK_LABEL_LINE =
  'The label checked here is the artwork inside the application, not a photo of a bottle.'

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

/*
 * `ARTWORK_DERIVED_CAVEAT` was here. It said, in two sentences under the row,
 * what the chip above the row and the source line inside it already say: this
 * came off the artwork that is also the label, so it could not have disagreed.
 * The API's own reason for the row now says the one thing none of those three
 * states, in one sentence. Removed 2026-08-31.
 */
