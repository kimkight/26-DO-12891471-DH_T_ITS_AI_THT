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
  ocr_confidence: number
  elapsed_ms: number
  ocr_ms: number
  external_call_made: boolean
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
