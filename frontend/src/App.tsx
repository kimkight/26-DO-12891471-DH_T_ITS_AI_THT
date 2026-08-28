/**
 * The whole interface: one screen, two tabs (FR-10, NFR-4, NFR-5).
 *
 * ## What this page claims to be, and what it refuses to claim
 *
 * The interface is dressed in the government palette: navy, a gold accent, and
 * white cards floating on a muted blue-grey field. That is a deliberate choice,
 * because the tool is about federal label compliance and a prototype with a
 * brand of its own would be answering the wrong question about whether it
 * belongs in this workflow. The surface around that palette is a soft, modern
 * product surface rather than a published form: segmented pill controls,
 * generous radii, layered shadows. The colours did not change with it.
 *
 * Dressing like federal work and *claiming to be* federal work are different
 * things, and this file is where the difference is enforced:
 *
 * - The first thing on every view, before the masthead, is a banner saying this
 *   is a prototype built for an employment assessment, that it is not an
 *   official TTB or Treasury system, and that nothing uploaded is stored.
 * - The footer names the author and the assignment.
 * - There is no TTB seal, no Treasury seal, no eagle, and no "An official
 *   website of the United States government" banner. Not a stylized one, not a
 *   recreated one, not an approximation. `src/__tests__/branding.test.tsx`
 *   fails if any of those appears.
 *
 * The agency's full name appears once, as plain text above the product name, at
 * the size and weight a subject line gets. It says what the tool is about. The
 * banner immediately above it has already said who built it and what it is not,
 * which is what keeps the two from being confused.
 *
 * NFR-4's first criterion is that the primary task is reachable from the
 * landing page with no navigation, so "Check one label" is the tab that is
 * already open. The batch tab is the second thing, not the first, because the
 * common case is one label and Sarah's 300-label drop is the exception.
 *
 * The tabs follow the ARIA tabs pattern: `role="tablist"`, arrow keys move
 * between tabs, `aria-selected` says which is current, and each panel is
 * labelled by its tab. That is a small amount of machinery for two tabs, and it
 * is here because the alternative, two buttons that swap content with no
 * announcement, leaves a screen reader user with no way to know the page
 * changed.
 *
 * They are drawn as a segmented pill control rather than as underlined tabs,
 * which is presentation and nothing else: the roles, the states and the key
 * handling below are unchanged. The active segment is carried by a fill, a
 * shadow and a weight change together, because a white pill on a pale track is
 * a weak signal on its own, and `aria-selected` is what is actually read out.
 *
 * Both panels stay mounted once opened, so a half-filled form is still there
 * after a look at the other tab. Only the hidden one carries `hidden`, which
 * takes it out of the accessibility tree and the tab order together.
 */
import { useRef, useState } from 'react'
import { BatchTab } from './components/BatchTab'
import { SingleLabelTab } from './components/SingleLabelTab'

const TABS = [
  { id: 'single', label: 'Check one label' },
  { id: 'batch', label: 'Check many labels' },
] as const

type TabId = (typeof TABS)[number]['id']

export default function App() {
  const [active, setActive] = useState<TabId>('single')
  const [opened, setOpened] = useState<Set<TabId>>(new Set(['single']))
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  function open(id: TabId) {
    setActive(id)
    setOpened((previous) => new Set(previous).add(id))
  }

  function onKeyDown(event: React.KeyboardEvent) {
    const index = TABS.findIndex((tab) => tab.id === active)
    let next: number
    if (event.key === 'ArrowRight') next = (index + 1) % TABS.length
    else if (event.key === 'ArrowLeft') next = (index - 1 + TABS.length) % TABS.length
    else if (event.key === 'Home') next = 0
    else if (event.key === 'End') next = TABS.length - 1
    else return
    event.preventDefault()
    open(TABS[next].id)
    tabRefs.current[TABS[next].id]?.focus()
  }

  return (
    <>
      {/*
        The skip link is the first thing in the tab order. The header is short,
        but the tab list sits between it and the form, and an agent who tabs
        should be able to reach the drop zone without passing through the
        chrome twice on every check.
      */}
      <a className="skip-link" href="#main">
        Skip to the label check
      </a>

      {/*
        Persistent, on every view, never dismissible, and above the masthead
        rather than below it. Its position is the point: an agent who reads one
        line of this page reads this one. It is not marked as an alert, because
        it is not an error to clear; it is a standing statement of what this is.
      */}
      <div className="prototype-banner">
        <p className="prototype-banner__text">
          <span className="prototype-banner__lead">
            Prototype built for an employment assessment.
          </span>{' '}
          Not an official TTB or Treasury system. Nothing you upload is stored.
        </p>
      </div>

      <header className="masthead">
        <div className="masthead__inner">
          {/*
            Plain text styling only. Not a wordmark, not a lockup, and not
            accompanied by any seal or emblem.
          */}
          <p className="masthead__agency">Alcohol and Tobacco Tax and Trade Bureau</p>
          <h1>TTB Label Verifier</h1>
          {/*
            The one accent-highlighted phrase on the page. Gold on navy is the
            pair that clears 4.5:1; the same gold on any light surface is
            illegible and is never used there. Emphasis used twice is emphasis
            used never, so there is no second one.
          */}
          <p className="masthead__subtitle">
            Compare label artwork against what the application says. This tool recommends.{' '}
            <span className="masthead__accent">You decide.</span>
          </p>
        </div>
      </header>

      <main id="main">
        <div
          className="tabs"
          role="tablist"
          aria-label="What you want to check"
          onKeyDown={onKeyDown}
        >
          {TABS.map((tab) => (
            <button
              key={tab.id}
              ref={(element) => {
                tabRefs.current[tab.id] = element
              }}
              className={`tab${active === tab.id ? ' tab--active' : ''}`}
              type="button"
              role="tab"
              id={`tab-${tab.id}`}
              aria-selected={active === tab.id}
              aria-controls={`panel-${tab.id}`}
              // Only the selected tab is in the tab order; the arrow keys move
              // between them from there. That is the ARIA tabs pattern, and it
              // stops a two-tab strip costing two tab stops before the form.
              tabIndex={active === tab.id ? 0 : -1}
              onClick={() => open(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {TABS.map((tab) => (
          <div
            key={tab.id}
            id={`panel-${tab.id}`}
            role="tabpanel"
            aria-labelledby={`tab-${tab.id}`}
            hidden={active !== tab.id}
          >
            {opened.has(tab.id) ? tab.id === 'single' ? <SingleLabelTab /> : <BatchTab /> : null}
          </div>
        ))}
      </main>

      <footer className="site-footer">
        <div className="site-footer__inner">
          <p>
            Nothing you upload is stored. Images and the values you type are held only for as long
            as the check takes, and the results live in this page until you leave it.
          </p>
          <p className="site-footer__attribution">
            Built by Kimberly D. Kight as a take-home assignment.
          </p>
        </div>
      </footer>
    </>
  )
}
