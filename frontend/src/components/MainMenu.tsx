import { useState } from 'react'
import CreateSession from './CreateSession'
import DeleteSession from './DeleteSession'

type Props = { role: string; onSignOut: () => void }

function MainMenu({ role, onSignOut }: Props) {
  const [creatingSession, setCreatingSession] = useState(false)
  const [deletingSession, setDeletingSession] = useState(false)

  if (creatingSession) {
    return <CreateSession onDone={() => setCreatingSession(false)} />
  }

  if (deletingSession) {
    return <DeleteSession onDone={() => setDeletingSession(false)} />
  }

  return (
    <section>
      <h2>Main menu</h2>
      {role === 'coach' && (
        <>
          <button onClick={() => setCreatingSession(true)}>Create Session</button>
          <button onClick={() => setDeletingSession(true)}>Delete Session</button>
        </>
      )}
      <button onClick={onSignOut}>Sign out</button>
    </section>
  )
}

export default MainMenu
