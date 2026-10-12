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

type MockResponse = { ok: boolean; status?: number; json: () => Promise<unknown> }

function mockApi(chatResponses: MockResponse[]) {
  const queue = [...chatResponses]
  const fetchMock = vi.fn((url: string) =>
    Promise.resolve(
      url.endsWith('/chat') ? queue.shift() : { ok: true, json: async () => leads },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function chatRequestBody(fetchMock: ReturnType<typeof mockApi>, index: number) {
  const chatCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/chat'))
  const [, init] = chatCalls[index] as unknown as [string, RequestInit]
  return JSON.parse(String(init.body))
}

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

  it('sends a question to the chat endpoint and shows the reply', async () => {
    const fetchMock = mockApi([
      { ok: true, json: async () => ({ reply: 'There are 342 open leads.', thread_id: 'thread-1' }) },
      { ok: true, json: async () => ({ reply: '112 of them came from Google.', thread_id: 'thread-1' }) },
    ])
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Open chat' }))
    expect(screen.getByRole('dialog', { name: 'Chat with leads' })).toBeTruthy()
    await user.type(screen.getByRole('textbox', { name: 'Message' }), 'How many leads are open?{Enter}')

    expect(await screen.findByText('There are 342 open leads.')).toBeTruthy()
    expect(screen.getByText('How many leads are open?')).toBeTruthy()
    expect(chatRequestBody(fetchMock, 0)).toEqual({ message: 'How many leads are open?', thread_id: null })

    await user.type(screen.getByRole('textbox', { name: 'Message' }), 'From Google?{Enter}')

    expect(await screen.findByText('112 of them came from Google.')).toBeTruthy()
    expect(chatRequestBody(fetchMock, 1)).toEqual({ message: 'From Google?', thread_id: 'thread-1' })
  })

  it('sends a suggested question when clicked', async () => {
    const fetchMock = mockApi([
      { ok: true, json: async () => ({ reply: '25 leads were closed in the last week.', thread_id: 't' }) },
    ])
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Open chat' }))
    await user.click(screen.getByRole('button', { name: 'How many leads were closed in the last week?' }))

    expect(await screen.findByText('25 leads were closed in the last week.')).toBeTruthy()
    expect(chatRequestBody(fetchMock, 0).message).toBe('How many leads were closed in the last week?')
  })

  it('keeps the conversation when the chat is closed and reopened', async () => {
    mockApi([{ ok: true, json: async () => ({ reply: 'There are 342 open leads.', thread_id: 't' }) }])
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Open chat' }))
    await user.type(screen.getByRole('textbox', { name: 'Message' }), 'How many leads are open?{Enter}')
    await screen.findByText('There are 342 open leads.')
    await user.click(screen.getByRole('button', { name: 'Close chat', expanded: true }))
    await user.click(screen.getByRole('button', { name: 'Open chat' }))

    expect(screen.getByText('There are 342 open leads.')).toBeTruthy()
  })

  it('shows an error message when the chat endpoint fails', async () => {
    mockApi([{ ok: false, status: 503, json: async () => ({}) }])
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Open chat' }))
    await user.type(screen.getByRole('textbox', { name: 'Message' }), 'hi{Enter}')

    expect(await screen.findByText(/model is unavailable/)).toBeTruthy()
  })

  it('disables sending an empty message', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: 'Open chat' }))

    expect(screen.getByRole('button', { name: 'Send message' }).hasAttribute('disabled')).toBe(true)
  })
})
