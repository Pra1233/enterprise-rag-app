import { Plus } from 'lucide-react'
import { useEffect, useState } from 'react'

import { ChatWindow } from '../components/chat/ChatWindow'
import type { Conversation } from '../types/chat.types'

const CONVERSATIONS_KEY = 'rag_conversations'

function loadConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(CONVERSATIONS_KEY)
    return raw ? (JSON.parse(raw) as Conversation[]) : []
  } catch {
    return []
  }
}

function createConversation(): Conversation {
  const now = Date.now()
  return {
    id: crypto.randomUUID(),
    title: new Date(now).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }),
    createdAt: now,
  }
}

const TITLE_MAX_LENGTH = 48

// ChatGPT-style auto-naming: once the first message in a fresh conversation
// is sent, retitle it from the question itself rather than leaving the
// generic timestamp. No extra LLM call — the question text IS the title.
function titleFromQuery(query: string): string {
  const singleLine = query.replace(/\s+/g, ' ').trim()
  return singleLine.length > TITLE_MAX_LENGTH ? `${singleLine.slice(0, TITLE_MAX_LENGTH - 1)}…` : singleLine
}

// Conversation history is a client-side-only convenience: the backend accepts
// a conversation_id but has no endpoint to list or fetch past conversations
// (see src/api/schemas/chat.py / src/api/routes/chat.py), so switching
// browsers or clearing site data loses this list.
export default function ChatPage() {
  const [conversations, setConversations] = useState<Conversation[]>(loadConversations)
  const [activeId, setActiveId] = useState<string>(() => conversations[0]?.id ?? '')

  useEffect(() => {
    if (!activeId && conversations.length === 0) {
      const first = createConversation()
      setConversations([first])
      setActiveId(first.id)
    }
  }, [activeId, conversations.length])

  useEffect(() => {
    localStorage.setItem(CONVERSATIONS_KEY, JSON.stringify(conversations))
  }, [conversations])

  const handleNewConversation = () => {
    const next = createConversation()
    setConversations((prev) => [next, ...prev])
    setActiveId(next.id)
  }

  const handleFirstMessage = (conversationId: string, query: string) => {
    setConversations((prev) =>
      prev.map((conv) => (conv.id === conversationId ? { ...conv, title: titleFromQuery(query) } : conv)),
    )
  }

  if (!activeId) return null

  return (
    <div className="flex h-full">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-gray-200 sm:flex dark:border-gray-700">
        <div className="p-2">
          <button
            type="button"
            onClick={handleNewConversation}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            <Plus className="size-4" /> New conversation
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-2">
          {conversations.map((conv) => (
            <button
              key={conv.id}
              type="button"
              onClick={() => setActiveId(conv.id)}
              className={`mb-1 block w-full truncate rounded-md px-3 py-2 text-left text-sm ${
                conv.id === activeId
                  ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300'
                  : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800'
              }`}
            >
              {conv.title}
            </button>
          ))}
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <ChatWindow
          key={activeId}
          conversationId={activeId}
          onFirstMessage={(query) => handleFirstMessage(activeId, query)}
        />
      </div>
    </div>
  )
}
