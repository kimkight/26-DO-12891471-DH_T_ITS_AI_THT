/**
 * The whole interface: one screen, two tabs (FR-10, NFR-4, NFR-5).
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

      <header className="masthead">
        <h1>Label check</h1>
        <p className="masthead__subtitle">
          Compare label artwork against what the application says. This tool recommends. You decide.
        </p>
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
        <p>
          Nothing you upload is stored. Images and the values you type are held only for as long as
          the check takes, and the results live in this page until you leave it.
        </p>
      </footer>
    </>
  )
}
