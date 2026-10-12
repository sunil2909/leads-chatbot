import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Send, Sparkles, X } from 'lucide-react'

type ChatMessage = {
  id: number
  role: 'user' | 'assistant' | 'error'
  text: string
}

type ChatResponse = {
  reply: string
  thread_id: string
}

const SUGGESTED_QUESTIONS = [
  'How many leads are open?',
  'How many leads were closed in the last week?',
  'Which lead sources have the most open leads?',
]

type ChatPanelProps = {
  apiBaseUrl: string
  open: boolean
  onClose: () => void
}

function ChatPanel({ apiBaseUrl, open, onClose }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [draft, setDraft] = useState('')
  const [threadId, setThreadId] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const nextId = useRef(0)
  const messagesEnd = useRef<HTMLDivElement>(null)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    messagesEnd.current?.scrollIntoView?.({ block: 'end' })
  }, [messages, sending])

  useEffect(() => {
    if (open) input.current?.focus()
  }, [open])

  function addMessage(role: ChatMessage['role'], text: string) {
    const message = { id: nextId.current++, role, text }
    setMessages((current) => [...current, message])
  }

  async function sendMessage(text: string) {
    const message = text.trim()
    if (!message || sending) return

    addMessage('user', message)
    setDraft('')
    setSending(true)

    try {
      const response = await fetch(`${apiBaseUrl}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, thread_id: threadId }),
      })
      if (!response.ok) {
        throw new Error(
          response.status === 503
            ? 'The assistant is starting up or the model is unavailable. Try again shortly.'
            : 'The assistant could not answer. Please try again.',
        )
      }
      const result: ChatResponse = await response.json()
      setThreadId(result.thread_id)
      addMessage('assistant', result.reply)
    } catch (error) {
      addMessage(
        'error',
        error instanceof TypeError
          ? 'Could not reach the API. Check that the backend is running.'
          : (error as Error).message,
      )
    } finally {
      setSending(false)
      input.current?.focus()
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void sendMessage(draft)
  }

  return (
    <section className="chat-panel" role="dialog" aria-label="Chat with leads" aria-modal="false" hidden={!open}>
      <header className="chat-header">
        <div className="chat-title-group">
          <span className="chat-avatar"><Sparkles size={17} /></span>
          <div>
            <h2>Lead assistant</h2>
            <p>
              <span className={`chat-status-dot${sending ? ' chat-status-busy' : ''}`} />
              {sending ? 'Thinking…' : 'Online · local model'}
            </p>
          </div>
        </div>
        <button type="button" className="chat-close" aria-label="Close chat" onClick={onClose}>
          <X size={18} />
        </button>
      </header>

      <div className="chat-body" aria-live="polite">
        <div className="chat-messages">
          <div className="assistant-message">
            <span className="message-kicker">LEADLINE ASSISTANT</span>
            <p>Ask me anything about your leads: counts, statuses, sources, or recent activity.</p>
            {messages.length === 0 && (
              <div className="chat-suggestions">
                {SUGGESTED_QUESTIONS.map((question) => (
                  <button
                    type="button"
                    key={question}
                    className="chat-suggestion"
                    onClick={() => void sendMessage(question)}
                  >
                    {question}
                  </button>
                ))}
              </div>
            )}
          </div>

          {messages.map((message) => (
            <div
              key={message.id}
              className={
                message.role === 'user'
                  ? 'user-message'
                  : `assistant-message${message.role === 'error' ? ' error-message' : ''}`
              }
            >
              {message.role !== 'user' && (
                <span className="message-kicker">
                  {message.role === 'error' ? 'CONNECTION ISSUE' : 'LEADLINE ASSISTANT'}
                </span>
              )}
              <p>{message.text}</p>
            </div>
          ))}

          {sending && (
            <div className="assistant-message typing-message" role="status" aria-label="Assistant is typing">
              <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
            </div>
          )}
          <div ref={messagesEnd} />
        </div>
      </div>

      <form className="chat-composer" onSubmit={handleSubmit}>
        <input
          ref={input}
          aria-label="Message"
          placeholder="Ask about your leads…"
          value={draft}
          maxLength={2000}
          onChange={(event) => setDraft(event.target.value)}
          disabled={sending}
        />
        <button type="submit" aria-label="Send message" disabled={sending || !draft.trim()}>
          <Send size={16} />
        </button>
      </form>
    </section>
  )
}

export default ChatPanel
