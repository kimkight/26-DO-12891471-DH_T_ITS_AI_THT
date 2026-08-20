import { useEffect, useState } from 'react'

interface Health {
  status: string
  service: string
  version: string
  environment: string
}

/**
 * Placeholder shell. The verification UI is not implemented yet; this view
 * exists only to prove the container serves the frontend and can reach the API.
 * See docs/04_USER_STORIES.md for the interface this will become.
 */
export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((response) => {
        if (!response.ok) throw new Error(`API returned ${response.status}`)
        return response.json()
      })
      .then(setHealth)
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Unknown error'))
  }, [])

  return (
    <main>
      <h1>TTB Label Verifier</h1>
      <p>
        Prototype scaffold. Label extraction and comparison are not implemented yet; see the
        repository documentation for scope and status.
      </p>
      <section aria-labelledby="status-heading">
        <h2 id="status-heading">Backend status</h2>
        {error && <p role="alert">Could not reach the API: {error}</p>}
        {!error && !health && <p>Checking...</p>}
        {health && (
          <dl>
            <dt>Status</dt>
            <dd>{health.status}</dd>
            <dt>Service</dt>
            <dd>{health.service}</dd>
            <dt>Version</dt>
            <dd>{health.version}</dd>
            <dt>Environment</dt>
            <dd>{health.environment}</dd>
          </dl>
        )}
      </section>
    </main>
  )
}
