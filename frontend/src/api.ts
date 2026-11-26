const BASE = '/api'

export type SignInResult = { role: string; landing: 'main_menu' | 'club_finances' }

export async function fetchMe(): Promise<SignInResult | null> {
  const response = await fetch(`${BASE}/auth/me`, { credentials: 'include' })
  if (response.status === 401) return null
  if (!response.ok) throw new Error('Failed to load session')
  return response.json()
}

export async function signIn(email: string, password: string): Promise<SignInResult> {
  const response = await fetch(`${BASE}/auth/sign-in`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ email, password }),
  })
  const body = await response.json()
  if (!response.ok) {
    throw new Error(body.detail ?? 'Sign-in failed')
  }
  return body
}

export async function signOut(): Promise<void> {
  await fetch(`${BASE}/auth/sign-out`, { method: 'POST', credentials: 'include' })
}
