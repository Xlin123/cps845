import { useEffect, useState } from 'react'
import { checkIn, fetchSessionsAttended } from '../api'
import CreateSession from './CreateSession'

type Props = { role: string; onSignOut: () => void }

function MainMenu({ role, onSignOut }: Props) {
  const [creatingSession, setCreatingSession] = useState(false)
  const [sessionsAttended, setSessionsAttended] = useState<number | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    fetchSessionsAttended()
      .then(setSessionsAttended)
      .catch(() => setSessionsAttended(null))
  }, [])

  async function handleCheckIn() {
    setMessage(null)
    try {
      const result = await checkIn()
      setSessionsAttended(result.sessionsAttended)
      setMessage(
        result.price > 0
          ? `Checked in. You owe ${result.price.toFixed(2)} for this session.`
          : 'Checked in.',
      )
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not check in')
    }
  }

  if (creatingSession) {
    return <CreateSession onDone={() => setCreatingSession(false)} />
  }

  return (
    <section>
      <h2>Main menu</h2>
      {sessionsAttended !== null && <p>Sessions attended: {sessionsAttended}</p>}
      {role === 'coach' && (
        <button onClick={() => setCreatingSession(true)}>Create Session</button>
      )}
      <button onClick={handleCheckIn}>Check In</button>
      {message && <p role="alert">{message}</p>}
      <button onClick={onSignOut}>Sign out</button>
    </section>
  )
}

export default MainMenu
