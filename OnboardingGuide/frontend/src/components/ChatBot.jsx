import { useState, useRef, useEffect } from 'react'
import { Send, Bot, User, Loader2, HelpCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

const INITIAL_MESSAGE = {
  role: 'bot',
  content:
    "Hello and welcome to Winmark Corporation! 👋\n\nI'm your onboarding assistant. I can help you with:\n\n- **Company information & culture**\n- **IT setup** (email, VPN, software)\n- **HR policies & benefits**\n- **Office facilities & parking**\n- **Finding coworkers** in the directory\n- **Training & development**\n\nWhat would you like to know?",
}

export default function ChatBot() {
  const [messages, setMessages] = useState([INITIAL_MESSAGE])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [showSuggestions, setShowSuggestions] = useState(true)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const QUICK_QUESTIONS = [
    'What should I expect on my first day?',
    'How do I set up my email?',
    'What is the PTO policy?',
    'How do I find a coworker?',
  ]

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async (text) => {
    const userMessage = text || input.trim()
    if (!userMessage) return

    setInput('')
    setShowSuggestions(false)
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage }),
      })

      if (!response.ok) throw new Error('Failed to get response')

      const data = await response.json()
      setMessages((prev) => [...prev, { role: 'bot', content: data.reply }])
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'bot',
          content:
            "Sorry, I'm having trouble connecting right now. Please try again or contact IT Help Desk at ext. 4357.",
        },
      ])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <>
      {/* Header */}
      <div className="bg-winmark-500 px-4 py-3 flex items-center gap-3">
        <div className="w-8 h-8 bg-white/20 rounded-full flex items-center justify-center">
          <Bot className="w-4 h-4 text-white" />
        </div>
        <div>
          <h3 className="text-white font-semibold text-sm">Onboarding Assistant</h3>
          <p className="text-winmark-100 text-xs">Ask me anything about getting started</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, index) => (
          <div
            key={index}
            className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}
          >
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${
                msg.role === 'user'
                  ? 'bg-winmark-100 text-winmark-600'
                  : 'bg-slate-100 text-slate-500'
              }`}
            >
              {msg.role === 'user' ? (
                <User className="w-3.5 h-3.5" />
              ) : (
                <Bot className="w-3.5 h-3.5" />
              )}
            </div>
            <div
              className={`max-w-[80%] px-3 py-2 rounded-xl text-sm leading-relaxed chat-message ${
                msg.role === 'user'
                  ? 'bg-winmark-500 text-white rounded-br-sm'
                  : 'bg-slate-100 text-slate-700 rounded-bl-sm'
              }`}
            >
              {msg.role === 'bot' ? (
                <ReactMarkdown
                  components={{
                    a: ({ node, ...props }) => (
                      <a {...props} target="_blank" rel="noopener noreferrer" className="text-winmark-600 underline" />
                    ),
                    strong: ({ node, ...props }) => <strong {...props} className="font-semibold" />,
                  }}
                >
                  {msg.content}
                </ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex gap-2">
            <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center flex-shrink-0">
              <Bot className="w-3.5 h-3.5 text-slate-500" />
            </div>
            <div className="bg-slate-100 px-3 py-2 rounded-xl rounded-bl-sm">
              <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Suggestions */}
      {showSuggestions && (
        <div className="px-4 pb-2">
          <div className="flex items-center gap-1.5 mb-2">
            <HelpCircle className="w-3 h-3 text-slate-400" />
            <span className="text-xs text-slate-400">Quick questions:</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {QUICK_QUESTIONS.map((q, i) => (
              <button
                key={i}
                onClick={() => sendMessage(q)}
                className="text-xs bg-slate-50 text-slate-600 px-2.5 py-1.5 rounded-full border border-slate-200 hover:bg-winmark-50 hover:text-winmark-600 hover:border-winmark-200 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="border-t border-slate-200 p-3">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your question..."
            disabled={loading}
            className="flex-1 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-winmark-300 focus:border-transparent disabled:opacity-50"
          />
          <button
            onClick={() => sendMessage()}
            disabled={loading || !input.trim()}
            className="p-2 bg-winmark-500 text-white rounded-lg hover:bg-winmark-600 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </>
  )
}
