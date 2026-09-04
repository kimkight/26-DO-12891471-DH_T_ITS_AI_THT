/**
 * One label's result, field by field (FR-10, FR-14, FR-15, ADR 0013, ADR 0018).
 *
 * The block the single-label tab has rendered under "What we found" since
 * v1.2.0, lifted out so that the batch tab renders exactly it when a row is
 * selected (ADR 0020). One component, not two that look alike: the summary
 * line, the note that the label came out of the application, the photograph
 * notes, the five cards and the closing line are the same code on both tabs,
 * so the two cannot disagree about what a result looks like without this file
 * changing.
 *
 * `idPrefix` is here because both tabs can be mounted at once and the cards
 * carry ids for their own headings; two results on one page would otherwise
 * share them (4.1.1).
 */
import { PhotoNotes } from './PhotoNotes'
import { ResultCard } from './ResultCard'
import { ARTWORK_LABEL_LINE } from '../lib/applicationSources'
import { summary } from '../lib/outcomes'
import type { VerificationResult } from '../types'

export function ResultDetail({
  result,
  idPrefix = 'card',
}: {
  result: VerificationResult
  idPrefix?: string
}) {
  return (
    <>
      {/*
        The summary line, and the reason it is not "5 of 5 fields match"
        (FR-14, ADR 0013). Where some of the five rows compared a value
        against the artwork it was read from, saying five would count
        fields that could not have come out any other way. The line says
        what is true instead: how many of the verifiable ones match, and
        how many were only read.
      */}
      <p className="summary-line">{summary(result.fields.map((field) => field.outcome))}</p>
      {/*
        The limit of what a search establishes is on the Help tab (US-28),
        under "Why is the brand name found but not judged for type size or
        placement?". It is a true and important sentence and it is not a
        sentence an agent needs in the middle of reading five results.

        `reasonWithoutLimit` still runs on each row. The API appends the
        limit to every searched reason because a caller with no interface
        has nowhere else to read it (OOS-4), and stripping it here is what
        keeps it from arriving on the row by the back door.
      */}
      {result.label_source === 'application_artwork' ? (
        <p className="footnote footnote--artwork">{ARTWORK_LABEL_LINE}</p>
      ) : null}
      <PhotoNotes
        photos={result.photos}
        document={result.application_document}
        idPrefix={idPrefix}
      />
      <div className="cards">
        {result.fields.map((field) => (
          <ResultCard
            key={field.name}
            field={field}
            warning={result.warning_detail}
            photoCount={result.photos.length}
            idPrefix={idPrefix}
          />
        ))}
      </div>
      <p className="footnote">This tool recommends. You decide.</p>
    </>
  )
}
