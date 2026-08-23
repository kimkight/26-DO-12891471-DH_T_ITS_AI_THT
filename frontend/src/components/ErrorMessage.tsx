/**
 * A failure, in the agent's terms (FR-9, NFR-4).
 *
 * `role="alert"` rather than the polite live region the results use: this
 * replaces the thing the agent was waiting for, so it interrupts.
 *
 * The API's own message is kept underneath the plain-language line rather than
 * discarded, because it is the half that names the limit (NFR-7). The plain
 * line says what to do; the detail says exactly what was wrong.
 */
import type { UiError } from '../lib/api'

export function ErrorMessage({ error }: { error: UiError }) {
  return (
    <div className="notice notice--error" role="alert">
      <p className="notice__headline">{error.message}</p>
      {error.detail ? <p className="notice__detail">{error.detail}</p> : null}
    </div>
  )
}
