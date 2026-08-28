/**
 * The large drop zone (NFR-4, NFR-5).
 *
 * A real `<input type="file">` with a `<label>` wrapped around it, not a div
 * with a click handler. That is what makes it keyboard reachable, focusable,
 * announced as a file input, and operable by every assistive technology that
 * already knows what a file input is. Drag and drop is added on top for the
 * agents who want it; nothing depends on it.
 *
 * The input is visually hidden rather than `display: none`, because a hidden
 * input is removed from the accessibility tree and from the tab order along
 * with it. The `.dropzone` wrapper carries the focus ring through
 * `:focus-within`, so focus is visible even though the control itself is not.
 *
 * `preview` turns the chosen file's name into a scan frame showing the
 * photograph itself. It is off by default and on for label artwork only: a PDF
 * of an application has nothing useful to show at this size, and the frame
 * would be an empty box with a filename under it.
 */
import { useId, useRef, useState } from 'react'
import { ScanFrame } from './Ui'

interface Props {
  label: string
  hint: string
  accept: string
  multiple?: boolean
  /** Show the chosen image in a scan frame instead of naming it. */
  preview?: boolean
  files: File[]
  onFiles: (files: File[]) => void
}

export function DropZone({
  label,
  hint,
  accept,
  multiple = false,
  preview = false,
  files,
  onFiles,
}: Props) {
  const inputId = useId()
  const describedBy = `${inputId}-hint`
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function accepted(list: FileList | null): File[] {
    if (!list) return []
    return multiple ? Array.from(list) : Array.from(list).slice(0, 1)
  }

  return (
    <div
      className={`dropzone${dragging ? ' dropzone--dragging' : ''}`}
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(event) => {
        event.preventDefault()
        setDragging(false)
        const dropped = accepted(event.dataTransfer.files)
        if (dropped.length) onFiles(dropped)
      }}
    >
      <label className="dropzone__label" htmlFor={inputId}>
        {label}
      </label>
      <p className="dropzone__hint" id={describedBy}>
        {hint}
      </p>
      <input
        ref={inputRef}
        id={inputId}
        className="dropzone__input"
        type="file"
        accept={accept}
        multiple={multiple}
        aria-describedby={describedBy}
        onChange={(event) => onFiles(accepted(event.target.files))}
      />
      {/*
        The frame carries the filename in its own caption, so the line below is
        suppressed when it is shown. Naming the file twice would be noise on
        screen and a duplicate for a screen reader working through the group.
      */}
      {preview && files.length === 1 ? <ScanFrame file={files[0]} /> : null}
      {files.length > 0 && !(preview && files.length === 1) ? (
        <p className="dropzone__chosen">
          {files.length === 1 ? files[0].name : `${files.length} files chosen`}
        </p>
      ) : null}
    </div>
  )
}
