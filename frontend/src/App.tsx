import { useEffect, useState } from 'react'
import { fetchMe, signOut, type SignInResult } from './api'
import SignIn from './components/SignIn'
import MainMenu from './components/MainMenu'
import ClubFinances from './components/ClubFinances'

function App() {
  const [session, setSession] = useState<SignInResult | null | undefined>(undefined)

  useEffect(() => {
    fetchMe()
      .then(setSession)
      .catch(() => setSession(null))
  }, [])

  async function handleSignOut() {
    await signOut()
    setSession(null)
  }

  return (
    <main>
      <h1>CM club</h1>
      {session === undefined ? null : session === null ? (
        <SignIn onSignedIn={setSession} />
      ) : session.landing === 'club_finances' ? (
        <ClubFinances onSignOut={handleSignOut} />
      ) : (
        <MainMenu onSignOut={handleSignOut} />
      )}
    </main>
  )
}

export default App
