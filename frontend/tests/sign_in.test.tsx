import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, it, vi } from 'vitest'
import App from '../src/App'

function mockFetchSequence(responses: Array<{ status: number; body: unknown }>) {
  let call = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => {
      const { status, body } = responses[Math.min(call, responses.length - 1)]
      call += 1
      return {
        ok: status < 400,
        status,
        json: async () => body,
      } as Response
    }),
  )
}

describe('Sign In', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('A confirmed Customer signs in and lands on the main menu', async () => {
    mockFetchSequence([
      { status: 401, body: { detail: 'Not signed in' } },
      { status: 200, body: { role: 'customer', landing: 'main_menu' } },
    ])

    render(<App />)
    await waitFor(() => screen.getByLabelText('Email address'))

    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'cara@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'correct horse battery' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await screen.findByRole('heading', { name: 'Main menu' })
  })

  it('The Treasurer signs in and lands on Club Finances', async () => {
    mockFetchSequence([
      { status: 401, body: { detail: 'Not signed in' } },
      { status: 200, body: { role: 'treasurer', landing: 'club_finances' } },
    ])

    render(<App />)
    await waitFor(() => screen.getByLabelText('Email address'))

    fireEvent.change(screen.getByLabelText('Email address'), {
      target: { value: 'tess@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Password'), {
      target: { value: 'treasurer passphrase' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await screen.findByRole('heading', { name: 'Club Finances' })
  })
})
