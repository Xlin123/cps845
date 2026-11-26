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

async function signInAsCoach() {
  const fetchMock = mockFetchSequence([
    { status: 401, body: { detail: 'Not signed in' } },
    { status: 200, body: { role: 'coach', landing: 'main_menu' } },
  ])

  render(<App />)
  await waitFor(() => screen.getByLabelText('Email address'))

  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: 'colm@example.com' },
  })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'coach passphrase' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  await screen.findByRole('button', { name: 'Create Session' })
  return fetchMock
}

describe('Session Created', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it("A session's length defaults to 60 minutes", async () => {
    await signInAsCoach()

    fireEvent.click(screen.getByRole('button', { name: 'Create Session' }))

    const lengthInput = await screen.findByLabelText('Length (minutes)')
    expect((lengthInput as HTMLInputElement).value).toBe('60')
  })

  it('Cancelling Create Session creates nothing', async () => {
    const fetchMock = await signInAsCoach()

    fireEvent.click(screen.getByRole('button', { name: 'Create Session' }))
    await screen.findByLabelText('Length (minutes)')
    const callsBeforeCancel = fetchMock.mock.calls.length

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    await screen.findByRole('heading', { name: 'Main menu' })
    expect(fetchMock.mock.calls.length).toBe(callsBeforeCancel)
  })
})
