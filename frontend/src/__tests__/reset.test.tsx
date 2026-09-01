/**
 * The reset control (US-29, NFR-4, NFR-5).
 *
 * The author: "add a reset option that clears the information so another
 * application can be uploaded."
 *
 * **What makes this more than a state reset is where focus lands and what a
 * screen reader hears.** A control that removes the five result cards, the
 * uploaded files and every typed value has taken away everything on the screen
 * including, if nothing is done about it, the focused element itself. A sighted
 * agent sees an empty form; an agent using a screen reader gets silence and
 * focus on the document body, which is the worst place focus can be. So the
 * announcement and the focus move are asserted as hard as the clearing is.
 *
 * There is no confirmation dialog and that is deliberate: nothing is stored, so
 * nothing is lost that cannot be re-uploaded, and a dialog is one more thing
 * between an agent who has finished one label and the next one.
 */
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BatchTab } from '../components/BatchTab'
import { SingleLabelTab } from '../components/SingleLabelTab'
import {
  applicationDocument,
  classification,
  fileClassification,
  parsedField,
  verification,
} from './fixtures'

const RESET = 'Clear and start another label'
const TOGGLE = 'Or type the application values'

const DOCUMENT = applicationDocument({
  fields: [
    parsedField('brand_name', 'DEL MAGUEY', { source: 'embedded_text' }),
    parsedField('class_type', 'MEZCAL', { source: 'embedded_text' }),
    parsedField('alcohol_content', null),
    parsedField('net_contents', null),
    parsedField('beverage_type', null),
  ],
  artwork_images_found: 1,
  artwork_images_read: 0,
  artwork_read: false,
  notes: [],
})

const CLASSIFIED = classification({
  files: [fileClassification('cola.pdf', 'application_document')],
  application_document: DOCUMENT,
  label_images: 0,
})

function stub() {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url: string) => ({
      ok: true,
      status: 200,
      json: async () => (url === '/api/classify' ? CLASSIFIED : verification()),
    })),
  )
}

function pdf(name = 'cola.pdf') {
  return new File([new Uint8Array([37, 80, 68, 70])], name, { type: 'application/pdf' })
}

function picker() {
  return screen.getByLabelText('Files for this label')
}

function announced() {
  return screen.getByRole('status', { name: 'Check result' }).textContent
}

afterEach(() => vi.unstubAllGlobals())

describe('where the control is, and what it is', () => {
  it('is not offered when there is nothing to clear', () => {
    stub()
    render(<SingleLabelTab />)

    expect(screen.queryByRole('button', { name: RESET })).not.toBeInTheDocument()
  })

  it('appears as soon as a file is chosen', async () => {
    const user = userEvent.setup()
    stub()
    render(<SingleLabelTab />)

    await user.upload(picker(), pdf())

    await waitFor(() => expect(screen.getByRole('button', { name: RESET })).toBeInTheDocument())
  })

  it('appears when the agent has typed something and uploaded nothing', async () => {
    const user = userEvent.setup()
    stub()
    render(<SingleLabelTab />)
    await user.click(screen.getByRole('button', { name: TOGGLE }))

    await user.type(screen.getByLabelText('Brand name'), 'Del Maguey')

    expect(screen.getByRole('button', { name: RESET })).toBeInTheDocument()
  })

  it('is a button rather than a link, so Space works and it is in the tab order', async () => {
    const user = userEvent.setup()
    stub()
    render(<SingleLabelTab />)
    await user.upload(picker(), pdf())

    const control = await screen.findByRole('button', { name: RESET })

    expect(control.tagName).toBe('BUTTON')
    // type="button" and not "submit": inside a <form>, a button without it runs
    // the check instead of clearing it.
    expect(control).toHaveAttribute('type', 'button')
    expect(control).not.toHaveAttribute('disabled')
  })

  it('asks nothing before it clears', async () => {
    const user = userEvent.setup()
    stub()
    render(<SingleLabelTab />)
    await user.upload(picker(), pdf())

    await user.click(await screen.findByRole('button', { name: RESET }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })
})

describe('reset from a completed check', () => {
  async function checkedThenReset() {
    const user = userEvent.setup()
    stub()
    render(<SingleLabelTab />)
    await user.upload(picker(), pdf())
    await waitFor(() => expect(screen.getByText(/values were filled in/)).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: 'Check this label' }))
    await waitFor(() => expect(document.querySelector('.summary-line')).not.toBeNull())
    await user.click(screen.getByRole('button', { name: RESET }))
    return user
  }

  it('returns every control to its initial value', async () => {
    await checkedThenReset()

    // The results, the uploaded file, the parsed summary and the check button's
    // own state: all of it back to where the page loaded.
    expect(document.querySelector('.summary-line')).toBeNull()
    expect(screen.queryByText('cola.pdf')).not.toBeInTheDocument()
    expect(screen.queryByText(/values were filled in/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Check this label' })).toBeDisabled()
    expect(screen.getByText('Upload a file to check.')).toBeInTheDocument()
  })

  it('clears every typed field, including ones the agent edited', async () => {
    const user = await checkedThenReset()
    await user.click(screen.getByRole('button', { name: TOGGLE }))

    expect(screen.getByLabelText('Brand name')).toHaveValue('')
    expect(screen.getByLabelText('Class or type designation')).toHaveValue('')
    expect(screen.getByLabelText('Alcohol content')).toHaveValue('')
    expect(screen.getByLabelText('Net contents')).toHaveValue('')
    expect(screen.getByLabelText('Beverage type')).toHaveValue('')
  })

  it('closes the disclosure it may have left open', async () => {
    const user = userEvent.setup()
    stub()
    render(<SingleLabelTab />)
    await user.click(screen.getByRole('button', { name: TOGGLE }))
    await user.type(screen.getByLabelText('Brand name'), 'Del Maguey')

    await user.click(screen.getByRole('button', { name: RESET }))

    expect(screen.getByRole('button', { name: TOGGLE })).toHaveAttribute('aria-expanded', 'false')
  })

  it('moves focus to the file picker', async () => {
    await checkedThenReset()

    // Not left on a removed button, and not dropped to the body. The picker is
    // where the agent goes next.
    await waitFor(() => expect(picker()).toHaveFocus())
  })

  it('announces that the form was cleared and is ready for the next label', async () => {
    await checkedThenReset()

    await waitFor(() => expect(announced()).toContain('The form was cleared'))
    expect(announced()).toContain('Upload the next label')
  })

  it('takes the control away with everything else', async () => {
    await checkedThenReset()

    expect(screen.queryByRole('button', { name: RESET })).not.toBeInTheDocument()
  })

  it('lets the same file be chosen again afterwards', async () => {
    /*
     * The reason the picker is remounted rather than emptied by hand. A file
     * input's value is not React's to control, and choosing a file identical to
     * the one already in it fires no change event, so an agent who cleared by
     * mistake could not simply re-choose the file they had.
     */
    const user = await checkedThenReset()

    await user.upload(picker(), pdf())

    await waitFor(() => expect(screen.getByText('cola.pdf')).toBeInTheDocument())
  })
})

describe('reset with files chosen but no check run', () => {
  it('does the same thing', async () => {
    const user = userEvent.setup()
    stub()
    render(<SingleLabelTab />)
    await user.upload(picker(), pdf())
    await waitFor(() => expect(screen.getByText(/values were filled in/)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: RESET }))

    expect(screen.queryByText('cola.pdf')).not.toBeInTheDocument()
    expect(screen.queryByText(/values were filled in/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Check this label' })).toBeDisabled()
    await waitFor(() => expect(picker()).toHaveFocus())
    expect(announced()).toContain('The form was cleared')
  })
})

describe('the batch view holds state, so it gets one too', () => {
  const BATCH_RESET = 'Clear and start another batch'

  function image(name: string) {
    return new File([new Uint8Array([137, 80])], name, { type: 'image/png' })
  }

  it('is not offered on an empty batch', () => {
    render(<BatchTab />)

    expect(screen.queryByRole('button', { name: BATCH_RESET })).not.toBeInTheDocument()
  })

  it('clears both pickers and returns the check to its disabled state', async () => {
    const user = userEvent.setup()
    render(<BatchTab />)
    await user.upload(screen.getByLabelText('Label images'), image('0001.png'))
    await user.upload(screen.getByLabelText('COLA documents'), pdf('0001.pdf'))

    await user.click(screen.getByRole('button', { name: BATCH_RESET }))

    expect(screen.queryByText('0001.png')).not.toBeInTheDocument()
    expect(screen.queryByText('0001.pdf')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Check .*labels/ })).toBeDisabled()
  })

  it('moves focus to the first picker and announces the clearing', async () => {
    const user = userEvent.setup()
    render(<BatchTab />)
    await user.upload(screen.getByLabelText('Label images'), image('0001.png'))

    await user.click(screen.getByRole('button', { name: BATCH_RESET }))

    await waitFor(() => expect(screen.getByLabelText('Label images')).toHaveFocus())
    expect(document.querySelector('[role="status"]')?.textContent).toContain(
      'The batch was cleared',
    )
  })
})
