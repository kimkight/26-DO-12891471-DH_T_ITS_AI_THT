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
 * only card with a tinted body and a ring around it, and the only one whose
 * icon is a triangle. It is the one an agent has to act on, so it is the one
 * that reads as unfinished.
 *
 * **The outcome chip leads the row.** An agent scanning five results is looking
 * for the one that needs them, and the thing they are looking for belongs at
 * the start of the line rather than at the end of it. The two values under it
 * are key-value rows: the label muted on the left, the value in bold on the
 * right, which is the shape a reader compares two things in.
 *
 * **One sentence per row, and no note under it (2026-08-31).** The card used to
 * carry a paragraph about provenance above the reason as well as the reason
 * itself, and on an artwork-derived row the two said the same thing twice at
 * length. Everything that paragraph said is already on the row in fewer words:
 * the outcome chip reads "Read from the artwork", the application value is
 * labelled with the source it came from, and the artwork-derived row carries
 * "Label artwork (same source as the label)" in its own key-value pair. The
 * paragraph was the third telling, and `quietScreen.test.tsx` holds the budget
 * that keeps a fourth from arriving.
 */
import { OutcomeBadge } from './OutcomeBadge'
import { ARTWORK_DERIVED_SOURCE, sourceChipLabel } from '../lib/applicationSources'
import { reasonWithoutLimit } from '../lib/labelSearch'
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
  idPrefix = 'card',
}: {
  field: FieldResult
  warning?: WarningResult
  /** How many photographs of the label were submitted (ADR 0007). */
  photoCount?: number
  /**
   * The prefix of the heading id, so two results on one page (the batch
   * tab's detail beside the single-label tab's result) do not share ids.
   */
  idPrefix?: string
}) {
  const { tone } = presentation(field.outcome)
  const isWarning = field.name === 'government_warning'
  // A row whose two sides are one reading of one picture (FR-14, ADR 0013).
  // It says so on the row, in its own key-value pair, because that is where an
  // agent is already looking when they wonder why this chip is not a match.
  const isArtworkDerived = field.outcome === 'artwork_derived'
  /*
   * A one-sided finding: the label carries an element 27 CFR requires and the
   * application declared nothing (FR-15, ADR 0018).
   *
   * **It has no application row at all**, and that is the presentation half of
   * the decision rather than tidying. The row used to print the same string in
   * both columns, because the value had been read off the artwork and written
   * into the application side, and an agent reading two identical values reads a
   * comparison. There was none. One value, one column, and the chip says what
   * kind of finding it is.
   */
  const isPresence = field.outcome === 'present'
  // Which photograph this value came from. Shown only when there was a choice
  // to make; on a one-photograph submission it says nothing new.
  const source = sourceLabel(field.source_photo, photoCount)

  return (
    <article className={`card card--${tone}`} aria-labelledby={`${idPrefix}-${field.name}`}>
      <header className="card__header">
        <OutcomeBadge outcome={field.outcome} />
        <h3 className="card__title" id={`${idPrefix}-${field.name}`}>
          {field.display_name}
        </h3>
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
        {isPresence ? null : (
          <Value
            label={
              isWarning
                ? 'Required by 27 CFR 16.21'
                : `On the application (${sourceChipLabel(field.application_value_source).toLowerCase()})`
            }
            value={field.application_value}
            missing="Not supplied"
          />
        )}
        {isArtworkDerived ? (
          <Value label="Source" value={ARTWORK_DERIVED_SOURCE} missing="" />
        ) : null}
      </dl>

      {/*
        The limit of a search hit comes off here for the same reason the
        bold-type note does: the API appends it to every searched row because a
        caller with no interface has nowhere else to read it (OOS-4), and this
        interface says it once above the rows instead of five times inside them.
      */}
      <p className="card__reason">
        {reasonWithoutLimit(reasonWithout(field.reason, warning?.bold_type_note))}
      </p>

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
  const capitalization = !warning.statement_found
    ? 'No warning statement was found, so there was no prefix to check.'
    : warning.prefix_legible === false
      ? warning.prefix_as_printed
        ? `The prefix was not read as "GOVERNMENT WARNING:"; it reads "${warning.prefix_as_printed}". Its capitalization was not checked, because it was not read (27 CFR 16.22(a)(2)).`
        : 'The prefix was not read at all, so its capitalization was not checked (27 CFR 16.22(a)(2)).'
      : warning.prefix_is_capitalized
        ? 'The prefix is in capital letters, as 27 CFR 16.22(a)(2) requires.'
        : `The prefix is printed as "${warning.prefix_as_printed}", not in capital letters. 27 CFR 16.22(a)(2) requires capitals.`

  return (
    <div className="card__detail">
      {warning.diff.length ? <WarningDiff warning={warning} /> : null}
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

/**
 * The character-level difference against 27 CFR 16.21 (FR-5, ADR 0012).
 *
 * **Shown so the agent can tell an OCR artifact from a real defect.** The
 * author's own COLA artwork reads the statement with one character wrong, and
 * "does not match word for word" is true of that and of a missing clause alike.
 * The difference between those two is the whole of the agent's decision, and
 * they cannot make it from a verdict.
 *
 * Each run is marked by text as well as by styling: a run the regulation
 * requires and the label does not show is prefixed "missing:", and a run on the
 * label the regulation does not have is prefixed "extra:". NFR-5's greyscale
 * rule applies here as much as to the outcome chips, and a difference conveyed
 * by a background colour would be invisible in print and to anyone who cannot
 * distinguish the two tints.
 *
 * `<del>` and `<ins>` rather than styled spans, because the two elements mean
 * exactly this and assistive technology already knows what they are.
 */
function WarningDiff({ warning }: { warning: WarningResult }) {
  const distance = warning.edit_distance ?? 0
  const characters = distance === 1 ? 'character' : 'characters'

  return (
    <>
      <h4 className="card__subtitle">
        {warning.near_miss
          ? `Difference from 27 CFR 16.21: ${distance} ${characters}`
          : 'Difference from 27 CFR 16.21'}
      </h4>
      {warning.near_miss ? (
        <p className="card__detail--note">
          A difference this small is as likely to be a reading error as a defect on the label. It is
          not a match, and it is not automatically a problem: check the label itself against the
          difference below.
        </p>
      ) : null}
      <p className="warning-diff">
        {warning.diff.map((segment, index) => {
          if (segment.kind === 'same') {
            return <span key={index}>{segment.text}</span>
          }
          if (segment.kind === 'missing') {
            return (
              <del className="warning-diff__missing" key={index}>
                <span className="visually-hidden"> missing: </span>
                {segment.text}
              </del>
            )
          }
          return (
            <ins className="warning-diff__added" key={index}>
              <span className="visually-hidden"> extra: </span>
              {segment.text}
            </ins>
          )
        })}
      </p>
      <p className="card__detail--note">
        Struck-through text is required by 27 CFR 16.21 and was not read from the label. Underlined
        text was read from the label and is not in the regulation.
      </p>
    </>
  )
}
