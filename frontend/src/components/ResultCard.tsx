/**
 * One field's result card (FR-10).
 *
 * FR-10's first criterion is that each row shows the field name, the value
 * found on the label, the value from the application, and the outcome. All four
 * are here, and the API's reason string is here too, because FR-3 requires the
 * evidence "so that an agent can judge the call rather than trust it". A card
 * that showed only the verdict would be asking for trust.
 *
 * The needs-review card is visually distinct from both of the others, which is
 * FR-10's third criterion, and it is distinct by more than colour: it is the
 * only card with a heavier left edge and the only one whose icon is a triangle.
 * It is the one an agent has to act on, so it is the one that reads as
 * unfinished.
 */
import { OutcomeBadge } from './OutcomeBadge'
import { presentation } from '../lib/outcomes'
import { sourceLabel } from '../lib/photos'
import type { FieldResult, WarningResult } from '../types'

/**
 * The reason line with the bold-type note taken off the end.
 *
 * The API appends that note to the warning field's reason, because a caller
 * with no interface has nowhere else to read it (OOS-4). This card does have
 * somewhere else: its own labelled Bold type section below, which repeats the
 * note verbatim. Printing it in both places says the same sentence twice on
 * one card.
 *
 * The note is removed only where it matches the API's own string exactly. If
 * the wording changes on the server and this build has not caught up, the
 * reason keeps it rather than losing it, so the disclosure survives the drift.
 */
function reasonWithout(reason: string, note: string | undefined): string {
  if (!note) return reason
  return reason.endsWith(note) ? reason.slice(0, -note.length).trim() : reason
}

function Value({
  label,
  value,
  missing,
}: {
  label: string
  value: string | null
  missing: string
}) {
  return (
    <div className="card__value">
      <dt>{label}</dt>
      <dd className={value ? '' : 'card__value--empty'}>{value || missing}</dd>
    </div>
  )
}

export function ResultCard({
  field,
  warning,
  photoCount = 1,
}: {
  field: FieldResult
  warning?: WarningResult
  /** How many photographs of the label were submitted (ADR 0007). */
  photoCount?: number
}) {
  const { tone } = presentation(field.outcome)
  const isWarning = field.name === 'government_warning'
  // Which photograph this value came from. Shown only when there was a choice
  // to make; on a one-photograph submission it says nothing new.
  const source = sourceLabel(field.source_photo, photoCount)

  return (
    <article className={`card card--${tone}`} aria-labelledby={`card-${field.name}`}>
      <header className="card__header">
        <h3 className="card__title" id={`card-${field.name}`}>
          {field.display_name}
        </h3>
        <OutcomeBadge outcome={field.outcome} />
      </header>

      <dl className="card__values">
        <Value
          label={source ? `On the label (${source.toLowerCase()})` : 'On the label'}
          value={field.label_value}
          missing={
            field.found_on_label
              ? 'Blank'
              : photoCount > 1
                ? 'Not found on any of your photos'
                : 'Not found on the label'
          }
        />
        <Value
          label={isWarning ? 'Required by 27 CFR 16.21' : 'On the application'}
          value={field.application_value}
          missing="Not supplied"
        />
      </dl>

      <p className="card__reason">{reasonWithout(field.reason, warning?.bold_type_note)}</p>

      {isWarning && warning ? <WarningDetail warning={warning} /> : null}
    </article>
  )
}

/**
 * The warning's capitalization check, reported separately from the wording
 * check (FR-6), and the bold-type note repeated verbatim (OOS-4).
 *
 * Separate because they fail for different reasons and an agent's next action
 * differs. Jenny Park's case is a statement whose wording is perfect and whose
 * prefix is in title case; collapsing the two into one verdict would tell her
 * the warning is wrong without telling her which half.
 *
 * The bold-type note is rendered from the API's own string rather than
 * restated here. It is the sentence that says this prototype does not check
 * bold type, and a paraphrase of it in the interface would be a second place
 * for OOS-4 to drift out of step.
 */
function WarningDetail({ warning }: { warning: WarningResult }) {
  const capitalization = warning.statement_found
    ? warning.prefix_is_capitalized
      ? 'The prefix is in capital letters, as 27 CFR 16.22(a)(2) requires.'
      : `The prefix is printed as "${warning.prefix_as_printed}", not in capital letters. 27 CFR 16.22(a)(2) requires capitals.`
    : 'No warning statement was found, so there was no prefix to check.'

  return (
    <div className="card__detail">
      <h4 className="card__subtitle">Capitalization of the prefix</h4>
      <p
        className={
          warning.prefix_is_capitalized === false ? 'card__detail--fail' : 'card__detail--note'
        }
      >
        {capitalization}
      </p>
      <h4 className="card__subtitle">Bold type</h4>
      <p className="card__detail--note">{warning.bold_type_note}</p>
    </div>
  )
}
