import { useEffect, useState } from 'react'
import { deleteSessions, fetchUpcomingSessions, type UpcomingSession } from '../api'

type Props = { onDone: () => void }

function DeleteSession({ onDone }: Props) {
  const [sessions, setSessions] = useState<UpcomingSession[] | null>(null)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchUpcomingSessions()
      .then(setSessions)
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load sessions'))
  }, [])

  function toggle(id: number) {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function confirmYes() {
    try {
      await deleteSessions([...selected])
      onDone()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete the sessions')
      setConfirming(false)
    }
  }

  if (sessions === null) {
    return error ? <p role="alert">{error}</p> : null
  }

  const selectedSessions = sessions.filter((s) => selected.has(s.id))

  if (confirming) {
    return (
      <section>
        <h2>Delete Session</h2>
        <p>Are you sure you want to delete these?</p>
        <ul>
          {selectedSessions.map((s) => (
            <li key={s.id}>{s.start}</li>
          ))}
        </ul>
        <button onClick={confirmYes}>Yes</button>
        <button onClick={onDone}>No</button>
      </section>
    )
  }

  return (
    <section>
      <h2>Delete Session</h2>
      {error && <p role="alert">{error}</p>}
      <table>
        <tbody>
          {sessions.map((s) => (
            <tr key={s.id}>
              <td>
                <label>
                  <input
                    type="checkbox"
                    checked={selected.has(s.id)}
                    onChange={() => toggle(s.id)}
                  />
                  {s.start}
                </label>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button disabled={selected.size === 0} onClick={() => setConfirming(true)}>
        Delete
      </button>
      <button onClick={onDone}>Cancel</button>
    </section>
  )
}

export default DeleteSession
