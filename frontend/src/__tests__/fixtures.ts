/** Response fixtures shaped exactly like backend/app/schemas.py returns. */
import type {
  ApplicationDocumentResult,
  BatchLine,
  ClassificationResult,
  FieldResult,
  FileClassification,
  Outcome,
  ParsedApplicationField,
  PhotoResult,
  VerificationResult,
  WarningResult,
} from '../types'

export const BOLD_TYPE_NOTE =
  'Bold type was not checked. 27 CFR 16.22(a)(2) also requires the prefix to be in bold, and this prototype does not check typeface.'

export function field(name: string, outcome: Outcome, overrides: Partial<FieldResult> = {}) {
  return {
    name,
    display_name: name.replace(/_/g, ' '),
    found_on_label: true,
    label_value: "STONE'S THROW",
    application_value: "Stone's Throw",
    score: 100,
    outcome,
    reason: `Reason for ${name}.`,
    source_photo: 1,
    application_value_source: 'typed',
    ...overrides,
  } satisfies FieldResult
}

/** One photograph of the label, read without incident (ADR 0007). */
export function photo(index = 1, overrides: Partial<PhotoResult> = {}): PhotoResult {
  return {
    index,
    origin: 'uploaded',
    orientation: {
      exif_orientation: null,
      exif_transposed: false,
      rotation_degrees: 0,
      method: 'osd',
      confidence: 13.7,
    },
    ocr_confidence: 95.4,
    read_path: {
      variant: 'preprocessed',
      preprocessed_confidence: 95.4,
      plain_confidence: null,
    },
    text_found: true,
    error: null,
    ...overrides,
  }
}

export function warningDetail(overrides: Partial<WarningResult> = {}): WarningResult {
  return {
    statement_found: true,
    prefix_as_printed: 'GOVERNMENT WARNING:',
    prefix_is_capitalized: true,
    body_matches_regulation: true,
    bold_type_checked: false,
    bold_type_note: BOLD_TYPE_NOTE,
    edit_distance: 0,
    near_miss: false,
    diff: [],
    ...overrides,
  }
}

export function verification(outcomes: Outcome[] = ['match', 'match', 'match', 'match', 'match']) {
  const names = [
    'brand_name',
    'class_type',
    'alcohol_content',
    'net_contents',
    'government_warning',
  ]
  return {
    fields: names.map((name, index) => field(name, outcomes[index] ?? 'match')),
    warning_detail: warningDetail(),
    photos: [photo()],
    ocr_confidence: 95.4,
    elapsed_ms: 540,
    ocr_ms: 530,
    external_call_made: false,
    application_document: null,
    files: [],
    label_source: 'uploaded_photographs',
    self_consistency_note: null,
  } satisfies VerificationResult
}

export function batchLine(
  filename: string,
  index: number,
  total: number,
  outcomes: Outcome[] | null,
  error?: { code: string; message: string },
): BatchLine {
  if (!outcomes) {
    return {
      filename,
      index,
      total,
      status: 'error',
      result: null,
      error: {
        code: error?.code ?? 'unreadable_image',
        message: error?.message ?? 'Bad image.',
        limit: null,
      },
    }
  }
  return { filename, index, total, status: 'ok', result: verification(outcomes), error: null }
}

/** One value read off an uploaded COLA document (FR-11, ADR 0008). */
export function parsedField(
  name: string,
  value: string | null,
  overrides: Partial<ParsedApplicationField> = {},
): ParsedApplicationField {
  return {
    name,
    display_name: name.replace(/_/g, ' '),
    value,
    found_on_document: value !== null,
    // The ordinary case is a value read out of the document's own text. A
    // fixture for the ADR 0010 case overrides this with 'embedded_artwork'.
    source: value === null ? 'absent' : 'embedded_text',
    ...overrides,
  }
}

/**
 * A read of an uploaded application. The defaults are the honest ones for
 * TTB F 5100.31 (04/2023): it carries a brand name and no class or type
 * designation, alcohol content or net contents, because those are not items on
 * the form (A-17).
 */
export function applicationDocument(
  overrides: Partial<ApplicationDocumentResult> = {},
): ApplicationDocumentResult {
  return {
    extraction_path: 'embedded_text',
    pages_read: 1,
    fields: [
      parsedField('brand_name', "STONE'S THROW"),
      parsedField('class_type', null),
      parsedField('alcohol_content', null),
      parsedField('net_contents', null),
      parsedField('beverage_type', null),
    ],
    fanciful_name: 'Small Batch Reserve',
    class_type_code: null,
    // No embedded artwork by default, which is the v1.0.1 shape of this
    // document. The ADR 0010 fixtures override all three.
    artwork_images_found: 0,
    artwork_images_read: 0,
    label_artwork_available: false,
    notes: [
      'The class or type designation is not an item on TTB F 5100.31 (04/2023).',
      'The alcohol content is not an item on TTB F 5100.31 (04/2023).',
      'The net contents is an item on TTB F 5100.31 (04/2023) only when it is blown, branded or embossed on the container.',
      "The type of product is item 5 on TTB F 5100.31 (04/2023), three checkboxes. A ticked box cannot be read from a document's text.",
    ],
    ...overrides,
  }
}

/** One sorted file, as POST /api/classify and POST /api/verify report it. */
export function fileClassification(
  filename: string,
  classifiedAs: FileClassification['classified_as'] = 'label_image',
  overrides: Partial<FileClassification> = {},
): FileClassification {
  const isDocument = classifiedAs === 'application_document'
  return {
    filename,
    classified_as: classifiedAs,
    basis: isDocument ? 'pdf_header' : 'no_form_markers',
    reason: isDocument
      ? 'This is a PDF, so we read it as the label application.'
      : 'We read this picture as a label.',
    used: true,
    ...overrides,
  }
}

/**
 * What POST /api/classify returns for one pile of files (FR-12, ADR 0011).
 *
 * The default is the ordinary two-file case: one application and one photo.
 */
export function classification(
  overrides: Partial<ClassificationResult> = {},
): ClassificationResult {
  return {
    files: [
      fileClassification('application.pdf', 'application_document'),
      fileClassification('label.png'),
    ],
    application_document: applicationDocument(),
    label_images: 1,
    application_error: null,
    ...overrides,
  }
}
