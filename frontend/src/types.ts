/**
 * The shapes the API returns, mirroring backend/app/schemas.py.
 *
 * Hand written rather than generated. The OpenAPI schema is available at
 * /openapi.json and a generator would keep these in step automatically, but
 * that is a build-time dependency and a code generation step for five types
 * that change when the requirements change. The trade is recorded here so the
 * next person can reverse it deliberately: if these drift, generate them.
 */

/**
 * FR-3's three outcomes, plus FR-2's "the application did not supply this",
 * plus FR-14's "this was read off the artwork and could not have disagreed".
 *
 * `artwork_derived` is not a verdict about agreement (ADR 0013). It marks a row
 * whose application value was read off the same label artwork that supplied the
 * label side, so the two values compared are one reading of one picture. It is
 * excluded from every count of fields that match, and it never carries a score.
 */
export type Outcome = 'match' | 'needs_review' | 'mismatch' | 'not_compared' | 'artwork_derived'

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
   * Which panel of the label the value was read from, or null where the field
   * was not found on the label. Filed artwork is often one flat sheet of
   * several panels; see `SegmentationDetail`.
   */
  label_region?: TextRegionDetail | null
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
  /**
   * Every embedded picture that was not big enough, or was the wrong shape, to
   * be label artwork, with the reason (v1.1.0). The commonest one on a filed
   * application is the applicant's own signature. The picture itself never
   * appears here.
   */
  artwork_images_rejected: RejectedImageDetail[]
  /** The page the chosen label artwork came from, or null when none was chosen. */
  label_artwork_page: number | null
  /** Whether one of them can stand in as the label side of the check. */
  label_artwork_available: boolean
}

/** One embedded picture that was not treated as candidate label artwork. */
export interface RejectedImageDetail {
  page: number
  width: number
  height: number
  reason: 'short_edge' | 'area' | 'aspect_ratio' | 'unreadable'
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
  method: 'osd' | 'osd_180_check' | 'unavailable' | 'disabled'
  confidence: number | null
  /**
   * The second opinion taken when Tesseract's own confidence in the turn fell
   * under the floor, or null when it did not (v1.1.0).
   */
  check: OrientationCheckDetail | null
}

/** What one candidate rotation scored when the image was actually read. */
export interface RotationScoreDetail {
  rotation_degrees: number
  confidence: number
  words: number
}

/**
 * The second opinion on a low-confidence orientation verdict (A-15).
 *
 * `candidates` always holds exactly two entries, and deliberately not four:
 * Tesseract's layout analysis already corrects a quarter-turn, so a score
 * cannot separate 0 from 90, and it separates a turn from its opposite cleanly.
 */
export interface OrientationCheckDetail {
  osd_rotation_degrees: number
  osd_confidence: number
  floor: number
  candidates: RotationScoreDetail[]
  chosen_rotation_degrees: number
  overrode_osd: boolean
}

/**
 * Whether preprocessing helped this photograph (v1.0.1).
 *
 * The pipeline reads the preprocessed image and, unless that read comes back
 * confident, reads the plain upright grayscale too and keeps whichever scored
 * higher. `plain_confidence` is null when the second read never ran.
 */
export interface ReadPathDetail {
  variant: 'preprocessed' | 'plain' | 'colour'
  preprocessed_confidence: number
  plain_confidence: number | null
  /**
   * Mean word confidence of the colour read, or null when the image carried no
   * colour a grayscale conversion would have discarded (v1.1.0).
   */
  colour_confidence: number | null
  /**
   * How the winning read was chosen. `coverage` is the case mean confidence
   * alone cannot decide: two reads equally confident about what each of them
   * read, one of which read more, because a word that was never read lowers no
   * score.
   */
  decided_by: 'short_circuit' | 'confidence' | 'coverage'
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
  /** How the sheet was cut into panels before its words were read. */
  segmentation?: SegmentationDetail
  text_found: boolean
  error: ErrorDetail | null
}

/**
 * How one photograph's sheet was cut into panels before it was read (FR-10).
 *
 * Filed label artwork is often one flat sheet carrying several panels side by
 * side, and a reader that assembles lines across the whole width of it splices
 * one panel's words into another panel's sentence. `columns` of 1 is a sheet
 * with no gutter wide enough to cut at, which is every single-panel label.
 */
export interface SegmentationDetail {
  columns: number
  blocks: number
  column_bounds: [number, number][]
}

/** Which panel of a segmented sheet one value came from, numbered from zero. */
export interface TextRegionDetail {
  column: number
  block: number
}

/**
 * One run of the character-level difference against 27 CFR 16.21 (FR-5).
 *
 * `kind` reads from the label's point of view, because that is what the agent
 * is looking at: `same` is text the two agree on, `added` is text on the label
 * the regulation does not have, and `missing` is text the regulation requires
 * that the label does not show.
 */
export interface WarningDiffSegment {
  kind: 'same' | 'added' | 'missing'
  text: string
}

/** The warning's two checks, reported separately (FR-6, OOS-4). */
export interface WarningResult {
  statement_found: boolean
  prefix_as_printed: string | null
  prefix_is_capitalized: boolean | null
  body_matches_regulation: boolean
  bold_type_checked: boolean
  bold_type_note: string
  /**
   * How many single-character edits separate the statement as printed from
   * 27 CFR 16.21. Zero when they match; null when none was found.
   */
  edit_distance: number | null
  /**
   * Whether the difference is small enough to be routed to a person rather than
   * reported as a flat mismatch (ADR 0012). **Never a pass**: the comparison is
   * still exact, and this is one of the two failing outcomes.
   */
  near_miss: boolean
  /** The character-level difference, in reading order. */
  diff: WarningDiffSegment[]
}

/**
 * Where the server's time went, measured rather than inferred (NFR-1).
 *
 * Every figure is a timer around the work it names. `unaccounted_ms` is the
 * only subtraction, and it is reported as leftover rather than attributed to
 * anything, which is the whole difference from what this replaced: the panel
 * used to subtract the server's figure from the browser's wall clock and tell
 * the agent the remainder was "sending the image".
 */
export interface PhaseTimings {
  /** Everything inside the request handler, from entry to response built. */
  total_ms: number
  classify_ocr_ms: number
  document_pdfium_ms: number
  document_ocr_ms: number
  page_ocr_ms: number
  artwork_ocr_ms: number
  label_ocr_ms: number
  compare_ms: number
  /** Every Tesseract pass in the request, and how many there were. */
  ocr_ms: number
  ocr_passes: number
  /** How many times the engine was invoked inside those passes (v1.1.0). */
  tesseract_reads: number
  accounted_ms: number
  unaccounted_ms: number
}

export interface VerificationResult {
  fields: FieldResult[]
  warning_detail: WarningResult
  photos: PhotoResult[]
  ocr_confidence: number
  /**
   * End to end inside the request handler: multipart handling, classification,
   * document parsing, image extraction, every OCR pass, the comparison and the
   * response. Before v1.1.0 this measured the label-side OCR span alone.
   */
  elapsed_ms: number
  ocr_ms: number
  /** The phase breakdown. Null on a response the server produced without one. */
  timings: PhaseTimings | null
  external_call_made: boolean
  application_document: ApplicationDocumentResult | null
  /** What each submitted file was taken to be, in submission order (FR-12). */
  files: FileClassification[]
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

/**
 * What one uploaded file was taken to be, and why (FR-12, ADR 0011).
 *
 * Reported so a misclassification is visible rather than silent. The single
 * upload decides what each file is from the file itself rather than from which
 * control it arrived in, which is right far more often than trusting the
 * control was; when it is wrong, the agent has to be able to see it.
 */
export interface FileClassification {
  filename: string
  classified_as: 'application_document' | 'label_image'
  basis:
    | 'pdf_header'
    | 'declared_pdf'
    | 'form_markers'
    | 'form_values'
    | 'no_form_markers'
    | 'undecodable'
  reason: string
  used: boolean
}

/** What POST /api/classify returns: the sorting, plus the application read. */
export interface ClassificationResult {
  files: FileClassification[]
  application_document: ApplicationDocumentResult | null
  label_images: number
  application_error: ErrorDetail | null
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
