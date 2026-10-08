import { useEffect, useState } from 'react'
import { ExternalLink, Mail, MessageCircle, Send, Sparkles, X } from 'lucide-react'
import './App.css'

type Lead = {
  lead_number: number
  lead_origin: string | null
  lead_source: string | null
  do_not_email: boolean | null
  do_not_call: boolean | null
  converted: boolean | null
  total_visits: number | null
  total_time_spent_on_website: number | null
  page_views_per_visit: number | null
  last_activity: string | null
  country: string | null
  specialization: string | null
  current_occupation: string | null
  lead_quality: string | null
  lead_profile: string | null
  city: string | null
  last_notable_activity: string | null
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080/api'

const columns: { key: keyof Lead; label: string; className?: string }[] = [
  { key: 'lead_number', label: 'Lead number', className: 'lead-number' },
  { key: 'lead_origin', label: 'Origin' },
  { key: 'lead_source', label: 'Source' },
  { key: 'do_not_email', label: 'Do not email' },
  { key: 'do_not_call', label: 'Do not call' },
  { key: 'converted', label: 'Converted' },
  { key: 'total_visits', label: 'Visits' },
  { key: 'total_time_spent_on_website', label: 'Website time' },
  { key: 'page_views_per_visit', label: 'Views / visit' },
  { key: 'last_activity', label: 'Last activity' },
  { key: 'country', label: 'Country' },
  { key: 'specialization', label: 'Specialization' },
  { key: 'current_occupation', label: 'Occupation' },
  { key: 'lead_quality', label: 'Lead quality' },
  { key: 'lead_profile', label: 'Lead profile' },
  { key: 'city', label: 'City' },
  { key: 'last_notable_activity', label: 'Notable activity' },
]

function displayValue(value: Lead[keyof Lead]): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  return String(value)
}

function App() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'empty' | 'error'>('loading')
  const [chatOpen, setChatOpen] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    async function loadLeads() {
      try {
        const response = await fetch(`${API_BASE_URL}/leads`, { signal: controller.signal })
        if (!response.ok) throw new Error('Leads request failed')
        const result: Lead[] = await response.json()
        setLeads(result)
        setLoadState(result.length ? 'ready' : 'empty')
      } catch {
        if (!controller.signal.aborted) setLoadState('error')
      }
    }

    void loadLeads()
    return () => controller.abort()
  }, [])

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Leadline home">
          <span className="brand-mark" aria-hidden="true">L</span>
          <span>leadline<span className="brand-period">.</span></span>
        </a>
        <nav aria-label="Main navigation">
          <a className="nav-link nav-link-active" href="#leads">Leads</a>
          <span className="phase-label"><span className="live-dot" />PoC workspace</span>
        </nav>
        <div className="topbar-meta"><span>PHASE 01</span><span className="meta-rule" />LOCAL DEMO</div>
      </header>

      <main className="workspace" id="leads">
        <section className="page-heading" aria-labelledby="page-title">
          <div className="heading-copy">
            <p className="eyebrow"><span>01</span> / LEAD INTELLIGENCE</p>
            <h1 id="page-title">Lead directory</h1>
            <p className="page-description">A closer look at every lead in your pipeline.</p>
          </div>
          <div className="record-summary" aria-live="polite">
            <span className="summary-count">{loadState === 'ready' ? leads.length : '—'}</span>
            <span className="summary-label">records loaded</span>
          </div>
        </section>

        <div className="table-heading">
          <div className="table-heading-title">
            <span className="table-marker" />
            <h2>All leads</h2>
            <span className="table-count">{loadState === 'ready' ? leads.length : ''}</span>
          </div>
          <p className="table-hint">SOURCE DATA <span>·</span> 17 FIELDS</p>
        </div>

        <section className="table-frame" aria-label="Lead data">
          <div className="table-scroll-region" role="region" aria-label="Lead records" tabIndex={0}>
            <table aria-label="Leads">
              <thead>
                <tr>
                  {columns.map(({ key, label, className }) => (
                    <th className={className} key={key} scope="col">{label}</th>
                  ))}
                  <th className="actions-column" scope="col">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loadState === 'ready' && leads.map((lead) => (
                  <tr key={lead.lead_number}>
                    {columns.map(({ key, className }) => (
                      <td className={className} key={key}>
                        {key === 'lead_number' ? (
                          <span className="lead-id">{lead.lead_number}</span>
                        ) : (
                          displayValue(lead[key])
                        )}
                      </td>
                    ))}
                    <td className="actions-column">
                      <div className="row-actions">
                        <button type="button" className="row-action" aria-label={`Email lead ${lead.lead_number}`} title="Email">
                          <Mail size={16} strokeWidth={1.8} />
                        </button>
                        <button type="button" className="row-action linkedin-action" aria-label={`LinkedIn lead ${lead.lead_number}`} title="LinkedIn">
                          <ExternalLink size={16} strokeWidth={1.8} />
                        </button>
                        <button type="button" className="row-action delete-action" aria-label={`Delete lead ${lead.lead_number}`} title="Delete">
                          <X size={17} strokeWidth={2} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {loadState !== 'ready' && (
              <div className="table-state" role="status">
                {loadState === 'loading' && <><span className="loading-mark" />Loading lead records</>}
                {loadState === 'empty' && <><span className="state-symbol">0</span>No leads to display</>}
                {loadState === 'error' && <><span className="state-symbol state-symbol-error">!</span>Could not load leads. Check the API connection.</>}
              </div>
            )}
          </div>
          <footer className="table-footer">
            <span><span className="footer-indicator" />{loadState === 'ready' ? 'All records' : 'Lead records'}</span>
            <span>LEADLINE <span className="footer-separator">/</span> 01</span>
          </footer>
        </section>
      </main>

      {chatOpen && (
        <section className="chat-panel" role="dialog" aria-label="Chat with leads" aria-modal="false">
          <header className="chat-header">
            <div className="chat-title-group">
              <span className="chat-avatar"><Sparkles size={17} /></span>
              <div><h2>Lead assistant</h2><p><span className="chat-status-dot" />Preview · inactive</p></div>
            </div>
            <button type="button" className="chat-close" aria-label="Close chat" onClick={() => setChatOpen(false)}>
              <X size={18} />
            </button>
          </header>
          <div className="chat-body">
            <div className="assistant-message">
              <span className="message-kicker">LEADLINE ASSISTANT</span>
              <p>Your lead conversations will appear here.</p>
              <span className="message-time">PHASE 02 CONNECTION</span>
            </div>
          </div>
          <form className="chat-composer">
            <input aria-label="Message" placeholder="Assistant unavailable in this preview" disabled />
            <button type="button" aria-label="Send message" disabled><Send size={16} /></button>
          </form>
        </section>
      )}

      <button
        type="button"
        className={`chat-launcher${chatOpen ? ' chat-launcher-open' : ''}`}
        aria-label={chatOpen ? 'Close chat' : 'Open chat'}
        aria-expanded={chatOpen}
        onClick={() => setChatOpen((open) => !open)}
      >
        {chatOpen ? <X size={21} /> : <MessageCircle size={21} />}
        {!chatOpen && <span className="launcher-label">Ask about leads</span>}
      </button>
    </div>
  )
}

export default App
