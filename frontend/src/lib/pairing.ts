/**
 * Pair label images with COLA documents by filename stem (FR-8, ADR 0009).
 *
 * The server pairs the same way and is the authority; this is here so the
 * interface can say what will happen before the batch is sent. An agent who
 * has dropped 300 images and 299 documents should find that out from the page,
 * not from one error line 20 minutes into a run.
 *
 * The rule, stated once: the stem is the filename with its final extension
 * removed, compared without regard to case. `0001-stones-throw.png` pairs with
 * `0001-stones-throw.pdf`. It must stay identical to `pairing_stem` in
 * `backend/app/batch.py`.
 */

export interface Pairing {
  /** Image filenames that have exactly one document, and vice versa. */
  paired: string[]
  /** Images with no document of the same stem. */
  imagesWithoutDocument: string[]
  /** Documents with no image of the same stem. */
  documentsWithoutImage: string[]
  /** Stems carried by more than one image, or by more than one document. */
  ambiguous: string[]
}

export function pairingStem(filename: string): string {
  const name = filename.trim().split('/').pop()?.split('\\').pop() ?? ''
  const cut = name.lastIndexOf('.')
  return (cut > 0 ? name.slice(0, cut) : name).toLowerCase()
}

function countByStem(files: File[]): Map<string, number> {
  const counts = new Map<string, number>()
  for (const file of files) {
    const stem = pairingStem(file.name)
    counts.set(stem, (counts.get(stem) ?? 0) + 1)
  }
  return counts
}

export function pair(images: File[], documents: File[]): Pairing {
  const imageStems = countByStem(images)
  const documentStems = countByStem(documents)
  const ambiguous = new Set<string>()
  for (const [stem, count] of imageStems) if (count > 1) ambiguous.add(stem)
  for (const [stem, count] of documentStems) if (count > 1) ambiguous.add(stem)

  const paired: string[] = []
  const imagesWithoutDocument: string[] = []
  for (const image of images) {
    const stem = pairingStem(image.name)
    if (ambiguous.has(stem)) continue
    if (documentStems.has(stem)) paired.push(image.name)
    else imagesWithoutDocument.push(image.name)
  }

  const documentsWithoutImage = documents
    .filter((document) => {
      const stem = pairingStem(document.name)
      return !ambiguous.has(stem) && !imageStems.has(stem)
    })
    .map((document) => document.name)

  return {
    paired,
    imagesWithoutDocument,
    documentsWithoutImage,
    ambiguous: [...ambiguous],
  }
}

/**
 * One sentence describing a pairing, for the page and for the live region.
 *
 * Written as one string used in both places rather than two that could drift:
 * NFR-5's point is that a screen reader user gets the same information a
 * sighted agent does, and the cheapest way to guarantee that is one sentence.
 */
export function describePairing(pairing: Pairing): string {
  const parts = [`${pairing.paired.length} ${plural(pairing.paired.length, 'pair')} ready to check`]
  if (pairing.imagesWithoutDocument.length) {
    parts.push(
      `${pairing.imagesWithoutDocument.length} ${plural(
        pairing.imagesWithoutDocument.length,
        'image',
      )} with no matching document`,
    )
  }
  if (pairing.documentsWithoutImage.length) {
    parts.push(
      `${pairing.documentsWithoutImage.length} ${plural(
        pairing.documentsWithoutImage.length,
        'document',
      )} with no matching image`,
    )
  }
  if (pairing.ambiguous.length) {
    parts.push(
      `${pairing.ambiguous.length} ${plural(pairing.ambiguous.length, 'name')} used more than once`,
    )
  }
  return `${parts.join(', ')}.`
}

function plural(count: number, word: string): string {
  return count === 1 ? word : `${word}s`
}
