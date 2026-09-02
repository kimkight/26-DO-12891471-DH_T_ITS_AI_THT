/**
 * Group a batch's files into rows by filename stem (FR-8, ADR 0009, ADR 0020).
 *
 * The server groups the same way and is the authority; this is here so the
 * page can lay out one pending row per label before the batch is sent and
 * fill each in, by position, as its line arrives. An agent who has dropped 300
 * files should see 300 rows appear and fill, not a table that grows in the
 * order the server happened to finish.
 *
 * The rule, stated once: the stem is the filename with its final extension
 * removed, compared without regard to case. `0001-stones-throw.png` and
 * `0001-stones-throw.pdf` are one row. It must stay identical to
 * `pairing_stem` in `backend/app/batch.py`, and since v1.3.0 it is: both sides
 * lower-case the stem with their language's plain lower-case mapping
 * (`toLowerCase` here, `str.lower` there). The server used `casefold`, which
 * also rewrites `ß` to `ss`, so `Straße.png` paired with `STRASSE.pdf` on the
 * server and not on the page (code review finding 21). The same vectors are
 * asserted on both sides, in `batchTable.test.tsx` and `test_batch.py`, so a
 * divergence fails a test rather than a batch.
 *
 * **What the stem no longer is** (ADR 0020). It used to be a precondition:
 * every image needed a document of the same name and the check stayed off
 * until both piles were chosen. Now it is a convenience. A row holding one
 * file is a valid row, checked for what it can be checked for, and what each
 * file is comes from the server's classification rather than from its
 * extension. So this module describes the rows; it no longer reports anything
 * as unmatched.
 */
import type { FileClassification } from '../types'

export function pairingStem(filename: string): string {
  const name = filename.trim().split('/').pop()?.split('\\').pop() ?? ''
  const cut = name.lastIndexOf('.')
  return (cut > 0 ? name.slice(0, cut) : name).toLowerCase()
}

export interface BatchGroup {
  /** 1-based, in order of first appearance, exactly as the server counts it. */
  position: number
  stem: string
  /** Indexes into the list of names the group was built from, in order. */
  indexes: number[]
}

/** Group filenames into rows, in order of first appearance of each stem. */
export function groupByStem(names: string[]): BatchGroup[] {
  const groups = new Map<string, BatchGroup>()
  names.forEach((name, index) => {
    const stem = pairingStem(name)
    const existing = groups.get(stem)
    if (existing) {
      existing.indexes.push(index)
      return
    }
    groups.set(stem, { position: groups.size + 1, stem, indexes: [index] })
  })
  return [...groups.values()]
}

/**
 * What the page knows about one file's side, before and after the server has
 * said. `null` is still being read; `'failed'` is a file the server could not
 * classify at all, which becomes a visible error row when the batch runs.
 */
export type KnownSide = FileClassification['classified_as'] | 'failed' | null

export type GroupShape = 'pair' | 'application' | 'image' | 'ambiguous' | 'failed' | 'reading'

/** What kind of row a group will be, from what is known of its files. */
export function groupShape(sides: KnownSide[]): GroupShape {
  if (sides.some((side) => side === null)) return 'reading'
  if (sides.some((side) => side === 'failed')) return 'failed'
  const documents = sides.filter((side) => side === 'application_document').length
  const labels = sides.filter((side) => side === 'label_image').length
  if (documents === 1 && labels === 1) return 'pair'
  if (documents === 1 && labels === 0) return 'application'
  if (documents === 0 && labels === 1) return 'image'
  return 'ambiguous'
}

/**
 * One sentence describing the rows, for the page and for the live region.
 *
 * Written as one string used in both places rather than two that could drift:
 * NFR-5's point is that a screen reader user gets the same information a
 * sighted agent does, and the cheapest way to guarantee that is one sentence.
 *
 * It counts labels, not files, because labels are what the agent is here to
 * check. It names only the shapes that are present, so a batch of twelve filed
 * applications reads "12 labels to check, each an application on its own"
 * rather than a list of zeroes.
 */
export function describeGroups(shapes: GroupShape[]): string {
  const total = shapes.length
  if (total === 0) return ''
  const count = (shape: GroupShape) => shapes.filter((entry) => entry === shape).length
  const head = `${total} ${plural(total, 'label')} to check`
  const parts: string[] = []
  const pairs = count('pair')
  const applications = count('application')
  const images = count('image')
  const ambiguous = count('ambiguous')
  const failed = count('failed')
  const reading = count('reading')
  if (pairs) parts.push(`${pairs} with an application and an image`)
  if (applications) {
    parts.push(
      applications === 1 ? '1 application on its own' : `${applications} applications on their own`,
    )
  }
  if (images) parts.push(images === 1 ? '1 image on its own' : `${images} images on their own`)
  if (ambiguous) {
    parts.push(`${ambiguous} with more than one file of the same kind, which cannot be checked`)
  }
  if (failed) parts.push(`${failed} with a file that could not be read`)
  if (reading) parts.push(`${reading} still being read`)
  if (parts.length === 1 && parts[0].startsWith(`${total} `)) {
    // Every row is the same shape: say it once rather than twice.
    return `${head}, ${describeAll(shapes[0], total)}.`
  }
  return `${head}: ${parts.join(', ')}.`
}

function describeAll(shape: GroupShape, total: number): string {
  switch (shape) {
    case 'pair':
      return 'each with an application and an image'
    case 'application':
      return total === 1 ? 'an application on its own' : 'each an application on its own'
    case 'image':
      return total === 1 ? 'an image on its own' : 'each an image on its own'
    case 'ambiguous':
      return 'each with more than one file of the same kind, which cannot be checked'
    case 'failed':
      return 'each with a file that could not be read'
    case 'reading':
      return 'still being read'
  }
}

function plural(count: number, word: string): string {
  return count === 1 ? word : `${word}s`
}
