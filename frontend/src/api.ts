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

export type CreateSessionFields = {
  date: string
  startTime: string
  lengthMinutes: number
  price: number
  overwriteIds?: number[]
}

export type SessionCollision = { id: number; start: string; lengthMinutes: number }

export class SessionCollisionError extends Error {
  canOverwrite: boolean
  collisions: SessionCollision[]

  constructor(message: string, canOverwrite: boolean, collisions: SessionCollision[]) {
    super(message)
    this.canOverwrite = canOverwrite
    this.collisions = collisions
  }
}

export async function createSession(fields: CreateSessionFields): Promise<void> {
  const response = await fetch(`${BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({
      date: fields.date,
      start_time: fields.startTime,
      length_minutes: fields.lengthMinutes,
      price: fields.price,
      overwrite_ids: fields.overwriteIds,
    }),
  })
  if (response.status === 409) {
    const body = await response.json()
    const detail = body.detail
    throw new SessionCollisionError(
      detail.detail,
      detail.can_overwrite,
      detail.collisions.map((c: { id: number; start: string; length_minutes: number }) => ({
        id: c.id,
        start: c.start,
        lengthMinutes: c.length_minutes,
      })),
    )
  }
  if (!response.ok) {
    const body = await response.json()
    throw new Error(body.detail ?? 'Could not create the session')
  }
}

export type UpcomingSession = { id: number; start: string; lengthMinutes: number; price: number }

export async function fetchUpcomingSessions(): Promise<UpcomingSession[]> {
  const response = await fetch(`${BASE}/sessions`, { credentials: 'include' })
  if (!response.ok) throw new Error('Could not load sessions')
  const body = await response.json()
  return body.map((s: { id: number; start: string; length_minutes: number; price: number }) => ({
    id: s.id,
    start: s.start,
    lengthMinutes: s.length_minutes,
    price: s.price,
  }))
}

export async function deleteSessions(sessionIds: number[]): Promise<void> {
  const response = await fetch(`${BASE}/sessions`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ session_ids: sessionIds }),
  })
  if (!response.ok) {
    const body = await response.json()
    const detail = typeof body.detail === 'string' ? body.detail : body.detail?.detail
    throw new Error(detail ?? 'Could not delete the sessions')
  }
}
