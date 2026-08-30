/**
 * The shapes the API returns, mirroring backend/app/schemas.py.
 *
 * Hand written rather than generated. The OpenAPI schema is available at
 * /openapi.json and a generator would keep these in step automatically, but
 * that is a build-time dependency and a code generation step for five types
 * that change when the requirements change. The trade is recorded here so the
 * next person can reverse it deliberately: if these drift, generate them.
 */

/** FR-3's three outcomes, plus FR-2's "the application did not supply this". */
export type Outcome = 'match' | 'needs_review' | 'mismatch' | 'not_compared'

/**
 * Where an application value came from (FR-11, ADR 0008, ADR 0010).
 *
 * These four are the precedence order, highest first. `parsed_from_form` is the
 * document's own text, whether an AcroForm field or a text layer;
 * `parsed_from_artwork` is a picture of the label embedded in that document,
 * read by OCR, which is weaker evidence and is only used where the text was
 * silent.
 */
export type ApplicationSource = 'typed' | 'parsed_from_form' | 'parsed_from_artwork' | 'absent'

/** Where inside an uploaded document one value was read (ADR 0010). */
export type DocumentValueSource = 'form_fields' | 'embedded_text' | 'embedded_artwork' | 'absent'

/** One field row (FR-3): both values, the score, the outcome, and why. */
export interface FieldResult {
  name: string
  display_name: string
  found_on_label: boolean
  label_value: string | null
  application_value: string | null
  score: number | null
  outcome: Outcome
  reason: string
  /**
   * Which submitted photograph this value was read from, numbered from 1
   * (ADR 0007). Null where the field was not found on any of them.
   */
  source_photo: number | null
  /**
   * Whether the agent typed this application value or it was read off an
   * uploaded COLA document (FR-11). A typed value always wins over a parsed
   * one, so this is what tells an agent which of the two they are looking at.
   */
  application_value_source: ApplicationSource
}

/** One value read off an uploaded COLA document (FR-11, ADR 0008). */
export interface ParsedApplicationField {
  name: string
  display_name: string
  value: string | null
  found_on_document: boolean
  /** Where in the document it was read: text, form field, or embedded artwork. */
  source: DocumentValueSource
}

/**
 * What an uploaded COLA document was read to say (FR-11, ADR 0008).
 *
 * Surfaced for confirmation, never silently trusted: the interface puts these
 * into the same editable fields an agent would have typed into, marked as read
 * from the application form, and the verification runs on what is in the fields.
 */
export interface ApplicationDocumentResult {
  extraction_path: 'form_fields' | 'embedded_text' | 'ocr'
  pages_read: number
  fields: ParsedApplicationField[]
  fanciful_name: string | null
  class_type_code: string | null
  notes: string[]
  /**
   * How many pictures embedded in the document were big enough to be label
   * artwork, and how many of those were read (ADR 0010). Zero read out of a
   * non-zero found is a different thing for an agent to act on than a document
   * carrying no pictures at all.
   */
  artwork_images_found: number
  artwork_images_read: number
  /** Whether one of them can stand in as the label side of the check. */
  label_artwork_available: boolean
}

/** How one photograph was turned before it was read (A-15). */
export interface OrientationDetail {
  /**
   * The EXIF orientation tag the file carried, 1 to 8, or null when it carried
   * none. Reported alongside what was done with it because a tag is a claim
   * about the pixels rather than a fact: a non-zero `rotation_degrees` on a
   * file that carried a tag means the tag was wrong and the quarter-turn check
   * corrected it.
   */
  exif_orientation: number | null
  exif_transposed: boolean
  rotation_degrees: number
  method: 'osd' | 'unavailable' | 'disabled'
  confidence: number | null
}

/**
 * Whether preprocessing helped this photograph (v1.0.1).
 *
 * The pipeline reads the preprocessed image and, unless that read comes back
 * confident, reads the plain upright grayscale too and keeps whichever scored
 * higher. `plain_confidence` is null when the second read never ran.
 */
export interface ReadPathDetail {
  variant: 'preprocessed' | 'plain'
  preprocessed_confidence: number
  plain_confidence: number | null
}

/**
 * One submitted photograph of the label (ADR 0007).
 *
 * Every photograph is reported, including the ones that failed. A submission
 * where two of three photographs were unreadable produced a result from one
 * photograph, and an agent deciding whether to trust it has to be able to see
 * that.
 */
export interface PhotoResult {
  index: number
  /**
   * Where this label image came from: a photograph the agent uploaded, or a
   * picture of the label lifted out of their application document (ADR 0010).
   */
  origin: 'uploaded' | 'application_artwork'
  orientation: OrientationDetail
  ocr_confidence: number
  read_path: ReadPathDetail
  text_found: boolean
  error: ErrorDetail | null
}

/** The warning's two checks, reported separately (FR-6, OOS-4). */
export interface WarningResult {
  statement_found: boolean
  prefix_as_printed: string | null
  prefix_is_capitalized: boolean | null
  body_matches_regulation: boolean
  bold_type_checked: boolean
  bold_type_note: string
}

export interface VerificationResult {
  fields: FieldResult[]
  warning_detail: WarningResult
  photos: PhotoResult[]
  ocr_confidence: number
  elapsed_ms: number
  ocr_ms: number
  external_call_made: boolean
  application_document: ApplicationDocumentResult | null
  /**
   * What the label side was read from (ADR 0010). `application_artwork` means
   * no photograph was uploaded and the artwork inside the application document
   * was used instead, which is a self-consistency check rather than a check of
   * a physical bottle.
   */
  label_source: 'uploaded_photographs' | 'application_artwork'
  /** Set only when `label_source` is `application_artwork`. */
  self_consistency_note: string | null
}

/** An error body (FR-9). It carries no field outcomes at all. */
export interface ErrorDetail {
  code: string
  message: string
  limit: string | null
}

/** One line of the batch NDJSON stream (FR-8, ADR 0006). */
export interface BatchLine {
  filename: string | null
  index: number
  total: number
  status: 'ok' | 'error'
  result: VerificationResult | null
  error: ErrorDetail | null
}

/** The five values an agent types in, in the A-14 column names. */
export interface ApplicationData {
  beverage_type: string
  brand_name: string
  class_type: string
  alcohol_content: string
  net_contents: string
}

export const EMPTY_APPLICATION: ApplicationData = {
  beverage_type: '',
  brand_name: '',
  class_type: '',
  alcohol_content: '',
  net_contents: '',
}
