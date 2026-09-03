/**
 * What happened to each submitted photograph (ADR 0007, A-15, FR-10).
 *
 * Two things are invisible in the result without this. A photograph the tool
 * turned upright and then read well, and a photograph the tool turned the wrong
 * way and then read badly, produce the same shape of response. And a
 * submission where two of three photographs were unreadable produced a real
 * result from one photograph, which an agent deciding whether to trust it needs
 * to know.
 *
 * Nothing is rendered for the ordinary case: one photograph, upright, read
 * without trouble. An interface that says "we did nothing to your photo" on
 * every check is noise, and NFR-4's benchmark is an agent who should not have
 * to read past anything.
 */
import { hasPhotoNotes, photoItemLabel, photoListHeading, photoNote } from '../lib/photos'
import type { PhotoResult } from '../types'

export function PhotoNotes({
  photos,
  idPrefix = 'card',
}: {
  photos: PhotoResult[]
  /** See `ResultCard`: two results on one page must not share heading ids. */
  idPrefix?: string
}) {
  if (!hasPhotoNotes(photos)) return null

  return (
    <section className="photo-notes" aria-labelledby={`${idPrefix}-photo-notes-heading`}>
      <h3 className="card__subtitle" id={`${idPrefix}-photo-notes-heading`}>
        {photoListHeading(photos)}
      </h3>
      <ul className="photo-notes__list">
        {photos.map((photo) => {
          const note = photoNote(photo)
          return (
            <li key={photo.index} className={photo.text_found ? '' : 'photo-notes__item--failed'}>
              <strong>{photoItemLabel(photo)}</strong>
              {note ? <> {note}</> : <> We read this one as it arrived.</>}
            </li>
          )
        })}
      </ul>
    </section>
  )
}
