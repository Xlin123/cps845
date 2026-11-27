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

async function signInAsCustomer(attended: number) {
  const fetchMock = mockFetchSequence([
    { status: 401, body: { detail: 'Not signed in' } },
    { status: 200, body: { role: 'customer', landing: 'main_menu' } },
    { status: 200, body: { sessions_attended: attended } },
  ])

  render(<App />)
  await waitFor(() => screen.getByLabelText('Email address'))

  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: 'cara@example.com' },
  })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'customer passphrase' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

  await screen.findByRole('button', { name: 'Check In' })
  return fetchMock
}

describe('Check In', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('Main menu shows sessions attended and a Check In button', async () => {
    await signInAsCustomer(4)

    await screen.findByText('Sessions attended: 4')
  })

  it('Checking in shows the price owed and updates sessions attended', async () => {
    const fetchMock = await signInAsCustomer(4)
    fetchMock.mockImplementationOnce(
      async () =>
        ({
          ok: true,
          status: 201,
          json: async () => ({
            session_start: '2026-12-03T23:00:00+00:00',
            checked_in_at: '2026-12-03T23:05:00+00:00',
            price: 15,
            sessions_attended: 5,
          }),
        }) as Response,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Check In' }))

    await screen.findByText('Sessions attended: 5')
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Checked in. You owe 15.00 for this session.',
    )
  })

  it('A refused check-in shows the reason and leaves sessions attended unchanged', async () => {
    const fetchMock = await signInAsCustomer(4)
    fetchMock.mockImplementationOnce(
      async () =>
        ({
          ok: false,
          status: 404,
          json: async () => ({ detail: 'There is no session to check in to right now' }),
        }) as Response,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Check In' }))

    await screen.findByText('There is no session to check in to right now')
    expect(screen.getByText('Sessions attended: 4')).toBeInTheDocument()
  })
})
