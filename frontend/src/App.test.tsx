import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'

const leads = [
  {
    lead_number: 660737,
    lead_origin: 'API',
    lead_source: 'Olark Chat',
    do_not_email: false,
    do_not_call: false,
    converted: false,
    total_visits: 0,
    total_time_spent_on_website: 0,
    page_views_per_visit: 0,
    last_activity: 'Page Visited on Website',
    country: null,
    specialization: 'Select',
    current_occupation: 'Unemployed',
    lead_quality: 'Low in Relevance',
    lead_profile: 'Select',
    city: 'Mumbai',
    last_notable_activity: 'Modified',
  },
]

describe('leads dashboard', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => leads,
      }),
    )
  })

  afterEach(() => {
    cleanup()
    vi.unstubAllGlobals()
  })

  it('renders fetched lead data and the right-side placeholder actions', async () => {
    render(<App />)

    expect(await screen.findByRole('cell', { name: '660737' })).toBeTruthy()
    expect(screen.getByRole('columnheader', { name: 'Actions' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Email lead 660737' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'LinkedIn lead 660737' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Delete lead 660737' })).toBeTruthy()
  })

  it('opens a placeholder chat panel without enabling message sending', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Open chat' }))

    expect(screen.getByRole('dialog', { name: 'Chat with leads' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Send message' }).hasAttribute('disabled')).toBe(
      true,
    )
  })
})