import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../src/App'

function mockFetchSequence(responses: Array<{ status: number; body: unknown }>) {
  let call = 0
  const fetchMock = vi.fn(async () => {
    const { status, body } = responses[Math.min(call, responses.length - 1)]
    call += 1
    return {
      ok: status < 400,
      status,
      json: async () => body,
    } as Response
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

async function signInAsCoach(upcomingSessions: unknown[]) {
  const fetchMock = mockFetchSequence([
    { status: 401, body: { detail: 'Not signed in' } },
    { status: 200, body: { role: 'coach', landing: 'main_menu' } },
    { status: 200, body: upcomingSessions },
  ])

  render(<App />)
  await waitFor(() => screen.getByLabelText('Email address'))

  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: 'colm@example.com' },
  })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'coach passphrase' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  await screen.findByRole('button', { name: 'Delete Session' })
  return fetchMock
}

const UPCOMING = [
  { id: 1, start: '2026-12-03T23:00:00+00:00', length_minutes: 60, price: 15 },
  { id: 2, start: '2026-12-05T23:00:00+00:00', length_minutes: 60, price: 15 },
]

describe('Session Deleted', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('The delete table lists only sessions that have not started', async () => {
    await signInAsCoach(UPCOMING)

    fireEvent.click(screen.getByRole('button', { name: 'Delete Session' }))

    await screen.findByText(UPCOMING[0].start)
    expect(screen.getByText(UPCOMING[1].start)).toBeInTheDocument()
    expect(screen.getAllByRole('checkbox')).toHaveLength(2)
  })

  it('Answering No deletes nothing and returns to the main menu', async () => {
    const fetchMock = await signInAsCoach(UPCOMING)

    fireEvent.click(screen.getByRole('button', { name: 'Delete Session' }))
    await screen.findByText(UPCOMING[0].start)
    fireEvent.click(screen.getAllByRole('checkbox')[0])
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
    await screen.findByText('Are you sure you want to delete these?')
    const callsBeforeNo = fetchMock.mock.calls.length

    fireEvent.click(screen.getByRole('button', { name: 'No' }))

    await screen.findByRole('heading', { name: 'Main menu' })
    expect(fetchMock.mock.calls.length).toBe(callsBeforeNo)
  })

  it('Cancelling the delete table deletes nothing', async () => {
    const fetchMock = await signInAsCoach(UPCOMING)

    fireEvent.click(screen.getByRole('button', { name: 'Delete Session' }))
    await screen.findByText(UPCOMING[0].start)
    const callsBeforeCancel = fetchMock.mock.calls.length

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await screen.findByRole('heading', { name: 'Main menu' })
    expect(fetchMock.mock.calls.length).toBe(callsBeforeCancel)
  })
})
