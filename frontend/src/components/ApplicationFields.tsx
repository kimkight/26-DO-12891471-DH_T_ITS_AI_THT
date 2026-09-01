/**
 * The application values: quiet about what was read, loud about what was not
 * (US-26, FR-13, FR-11, FR-3, NFR-4, NFR-5).
 *
 * The author's instruction on 2026-08-29, after the single upload: "Collapse
 * the form fields and only expand if there is something that isn't read in from
 * the application or picture."
 *
 * Session 10 put the five typed fields behind a disclosure, collapsed on load.
 * This is the next step, and it is about what happens *after* something has been
 * processed rather than before. Five text boxes shown after a document has
 * already answered four of them is a form asking an agent to re-read work the
 * tool has done. So:
 *
 * * **A value that was read is a summary line.** Read-only, one line, with the
 *   value and a chip saying where it came from. Nothing to type in, nothing to
 *   tab through.
 * * **A value that was not read is an editable field, shown.** Not behind
 *   anything. It is the only thing left to do, so it is the only thing on
 *   screen that looks like work. Focus moves to the first one and the reason is
 *   announced.
 * * **Everything read stays editable behind one disclosure**, "Review the
 *   values", collapsed. FR-3 says the agent judges, so a value they disagree
 *   with has to be correctable; it just does not have to be in the way.
 *
 * **Where the gap fields live, and why they are not inside the disclosure.**
 * The instruction says the fields should expand when something was not read.
 * Showing the missing field directly is the same outcome with one fewer moving
 * part: the agent sees exactly one box, in the place a box belongs, rather than
 * a panel opening onto five of which one matters. What is kept from the
 * disclosure idea is everything that made it good: focus lands on the missing
 * field, the page scrolls to it, and a live region says which field and why.
 *
 * **Three sources, not four.** A value on this side of the check comes from the
 * agent, from the application document's text, or from label artwork embedded
 * in that document (ADR 0010). It never comes from a photograph of the label:
 * that is the other side of the comparison, and taking the application value
 * off the label would mean comparing the label against itself. The chips say
 * only what is true.
 *
 * **Beverage type keeps its own line**, because the reason it is missing is a
 * fact about the form rather than about this document: item 5 is three check
 * marks, and a text layer prints the caption of an unticked box exactly as it
 * prints the caption of a ticked one (ADR 0008). It is never compared, so it
 * never takes focus and it is never a gap in the check.
 */
import { useEffect, useRef } from 'react'
import {
  BEVERAGE_TYPES,
  TEXT_FIELDS,
  TYPED_FIELDS_PANEL,
  gapAnnouncement,
} from '../lib/applicationFields'
import type { SourceMap } from '../lib/applicationFields'
import { fieldSourceMark, sourceChipLabel } from '../lib/applicationSources'
import type { ApplicationData, ApplicationSource } from '../types'

interface Props {
  application: ApplicationData
  /** Where each value came from, for the values that arrived from a document. */
  sources: SourceMap
  /** Whether anything has been uploaded and read yet. */
  processed: boolean
  /**
   * The compared values the upload did not supply, decided when it was read.
   *
   * **Decided once, not derived from what is currently in the boxes.** A field
   * that moved between the two sections as the agent typed would remount under
   * them: clearing a value to retype it would drop focus after the first
   * keystroke. What the upload supplied is a fact about the upload, and it does
   * not change because someone is editing.
   */
  gaps: (keyof ApplicationData)[]
  /**
   * The values the upload has not supplied *yet*, because the artwork they are
   * printed on is read by the check rather than by the prefill pass (ADR 0017).
   *
   * A third state, and it has to be a third state. These are not gaps: nothing
   * is being asked of the agent, so no box opens inline and nothing takes
   * focus. Nor are they read: there is no value to summarise, and a summary
   * line with an empty value beside a chip saying where it came from would be
   * the interface reporting a reading that has not happened. They stay
   * editable behind the disclosure, because an agent who wants to type one
   * before the check still may, and FR-11's precedence still makes theirs win.
   */
  pending?: (keyof ApplicationData)[]
  /** The disclosure's state, held by the parent because it is set from outside. */
  open: boolean
  onToggle: () => void
  onChange: (name: keyof ApplicationData, value: string) => void
  /** Called with the sentence to announce when the gaps change. */
  onGapNews: (news: string) => void
}

/** One value that was read, as a line rather than as a box. */
function SummaryLine({
  label,
  value,
  source,
}: {
  label: string
  value: string
  source: ApplicationSource
}) {
  // No caveat line under the chip. The chip is the caveat: it names the source
  // in four words, and a sentence repeating it was the third telling of
  // something the upload card says once above (2026-08-31).
  return (
    <div className="value-line">
      <span className="value-line__label">{label}</span>
      <span className="value-line__value">{value}</span>
      <span className={`chip chip--${source === 'typed' ? 'navy' : 'gold'}`}>
        {sourceChipLabel(source)}
      </span>
    </div>
  )
}

export function ApplicationFields({
  application,
  sources,
  processed,
  gaps: missing,
  pending = [],
  open,
  onToggle,
  onChange,
  onGapNews,
}: Props) {
  const gaps = TEXT_FIELDS.filter((field) => missing.includes(field.name))
  // Everything that is not a gap stays editable behind the disclosure, pending
  // values included. Only the ones with something in them are summarised.
  const editable = TEXT_FIELDS.filter((field) => !missing.includes(field.name))
  const read = editable.filter((field) => !pending.includes(field.name))
  const firstGapRef = useRef<HTMLInputElement>(null)

  /*
   * Focus the first missing field once something has been processed and left a
   * gap, and say why. It happens after the render because the field does not
   * exist until the gap does, and it happens once per set of gaps rather than
   * on every keystroke: the dependency is the list of missing field names, so
   * typing into one does not re-fire while the others are still empty.
   */
  const gapKey = gaps.map((field) => field.name).join(',')
  const announced = useRef('')
  useEffect(() => {
    if (!processed) return
    if (announced.current === gapKey) return
    announced.current = gapKey
    if (!gapKey) {
      onGapNews('')
      return
    }
    onGapNews(gapAnnouncement(gaps.map((field) => field.label.toLowerCase())))
    const field = firstGapRef.current
    field?.focus()
    // Guarded rather than called: `scrollIntoView` is not implemented in jsdom,
    // and a layout convenience must not be able to take the whole component
    // down in an environment that does not have it.
    field?.scrollIntoView?.({ block: 'center', behavior: 'smooth' })
    // `gaps` and `onGapNews` are derived from `gapKey` and from the parent's
    // stable callback; listing them would re-run this on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processed, gapKey])

  function textField(field: (typeof TEXT_FIELDS)[number], isFirstGap = false) {
    const mark = fieldSourceMark(sources[field.name] ?? 'absent')
    const describedBy = [
      field.hint ? `${field.name}-hint` : null,
      mark ? `${field.name}-from-form` : null,
    ]
      .filter(Boolean)
      .join(' ')
    return (
      <div className="field" key={field.name}>
        <label htmlFor={field.name}>{field.label}</label>
        {mark ? (
          <p className="field__source" id={`${field.name}-from-form`}>
            {mark}
          </p>
        ) : null}
        {field.hint ? (
          <p className="field__hint" id={`${field.name}-hint`}>
            {field.hint}
          </p>
        ) : null}
        <input
          ref={isFirstGap ? firstGapRef : undefined}
          id={field.name}
          name={field.name}
          type="text"
          autoComplete="off"
          aria-describedby={describedBy || undefined}
          value={application[field.name]}
          onChange={(event) => onChange(field.name, event.target.value)}
        />
      </div>
    )
  }

  const beverageSource = sources.beverage_type
  const beverageRead = !missing.includes('beverage_type')

  /**
   * The beverage type control, rendered in exactly one place at a time.
   *
   * Its hint changes with the situation, and the change is the ADR 0008 truth
   * rather than a rewording: before anything is processed it says what the
   * field is for, and after a document has been read without settling the type
   * it says why. Item 5 is three check boxes; a text layer prints the caption of
   * an unticked box exactly as it prints the caption of a ticked one, so the
   * boxes are sampled off the rendered page instead (ADR 0016). Where that did
   * not separate one box from the other two, the agent chooses.
   */
  function beverageField() {
    return (
      <div className="field">
        <label htmlFor="beverage_type">Beverage type</label>
        {/*
          What the beverage type is for went to Help (US-28), under "Where does
          beverage type come from?". The sentence that stays is the one that is
          about *this* document rather than about the field: item 5's boxes were
          looked at and did not settle it, so the agent chooses. On a document
          that did settle it there is nothing to say and nothing is said.
        */}
        {processed && !beverageRead ? (
          <p className="field__hint" id="beverage_type-hint">
            Item 5&rsquo;s boxes were read from the page and none of them stood out.
          </p>
        ) : null}
        <select
          id="beverage_type"
          name="beverage_type"
          value={application.beverage_type}
          aria-describedby={processed && !beverageRead ? 'beverage_type-hint' : undefined}
          onChange={(event) => onChange('beverage_type', event.target.value)}
        >
          {BEVERAGE_TYPES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    )
  }

  return (
    <div className="values">
      {/*
        Before anything has been uploaded there is nothing to summarise, so this
        is exactly the Session 10 layout: one collapsed disclosure over all five
        boxes, for the agent reading the values off another screen.
      */}
      {processed && read.length ? (
        <div className="values__read">
          <h3 className="card__subtitle">Read from your upload</h3>
          {read.map((field) => (
            <SummaryLine
              key={field.name}
              label={field.label}
              value={application[field.name]}
              source={sources[field.name] ?? 'typed'}
            />
          ))}
        </div>
      ) : null}

      {processed && gaps.length ? (
        <div className="values__gaps">
          <h3 className="card__subtitle">
            {gaps.length === 1 ? 'One value was not read' : `${gaps.length} values were not read`}
          </h3>
          <p className="field__hint">
            Enter it here, or upload a clearer file; an empty box is reported as not compared rather
            than as a mismatch.
          </p>
          {gaps.map((field, index) => textField(field, index === 0))}
        </div>
      ) : null}

      {/*
        Beverage type, on its own line, always. It is never compared, so it is
        never a gap in the check and never takes focus; but the reason it is
        usually missing is a fact about the form rather than about this
        document, and an agent who is not told that goes looking for a box that
        cannot be read (ADR 0008).
      */}
      {processed ? (
        <div className="values__beverage">
          {beverageRead ? (
            <SummaryLine
              label="Beverage type"
              value={application.beverage_type}
              source={beverageSource ?? 'typed'}
            />
          ) : (
            beverageField()
          )}
        </div>
      ) : null}

      {/*
        The disclosure. Before anything is processed it holds all five boxes and
        is labelled as the way to type them; afterwards it holds the ones that
        were read, so a value the agent disagrees with is still theirs to change
        (FR-3). It stays collapsed either way until the agent opens it.

        A button with aria-expanded and aria-controls rather than <details>,
        because the open state is set from outside this component as well as
        from the control. The panel keeps its contents in the DOM and hides them
        with `hidden`, so the fields leave the tab order and the accessibility
        tree together rather than one without the other.
      */}
      <div className="disclosure">
        <button
          className="button button--quiet disclosure__toggle"
          type="button"
          aria-expanded={open}
          aria-controls={TYPED_FIELDS_PANEL}
          onClick={onToggle}
        >
          <span className="disclosure__marker" aria-hidden="true" />
          {processed && read.length ? 'Review the values' : 'Or type the application values'}
        </button>

        <div className="disclosure__panel" id={TYPED_FIELDS_PANEL} hidden={!open}>
          <p className="field__hint">
            The check runs on whatever is in these boxes; a value you type wins, and an empty box is
            not compared.
          </p>

          {(processed ? editable : TEXT_FIELDS).map((field) => textField(field))}

          {/*
            The beverage type control lives here when it was read, and inline
            above when it was not, so there is exactly one of it on the page and
            an agent can always change it (FR-3).
          */}
          {!processed || beverageRead ? beverageField() : null}
        </div>
      </div>
    </div>
  )
}
