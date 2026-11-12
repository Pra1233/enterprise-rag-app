import { motion } from 'framer-motion'
import { MessageSquare, Trash2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { useChat } from '../../hooks/useChat'
import { EmptyState } from '../common/EmptyState'
import { ChatInput } from './ChatInput'
import { ChatMessageBubble } from './ChatMessage'

interface ChatWindowProps {
  conversationId: string
  onFirstMessage?: (query: string) => void
}

export function ChatWindow({ conversationId, onFirstMessage }: ChatWindowProps) {
  const [documentTypeFilter, setDocumentTypeFilter] = useState('')
  const { messages, sendMessage, stopGeneration, clearConversation, isStreaming } = useChat(
    conversationId,
    documentTypeFilter || undefined,
    onFirstMessage,
  )
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-gray-200 px-4 py-2 dark:border-gray-700">
        <span className="text-xs text-gray-400">
          {messages.length === 0 ? 'New conversation' : `${Math.ceil(messages.length / 2)} message pair(s)`}
        </span>
        <button
          type="button"
          onClick={clearConversation}
          disabled={messages.length === 0}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-gray-500 hover:bg-gray-100 disabled:opacity-40 dark:text-gray-400 dark:hover:bg-gray-800"
        >
          <Trash2 className="size-3.5" /> Clear conversation
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 ? (
          <EmptyState
            icon={MessageSquare}
            title="Ask anything about your documents"
            description="Your uploaded and indexed PDFs are used as context, with cited sources."
          />
        ) : (
          <div className="flex flex-col gap-4">
            {messages.map((message) => (
              <motion.div
                key={message.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2, ease: 'easeOut' }}
              >
                <ChatMessageBubble message={message} />
              </motion.div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <ChatInput
        onSend={sendMessage}
        onStop={stopGeneration}
        isStreaming={isStreaming}
        documentTypeFilter={documentTypeFilter}
        onDocumentTypeFilterChange={setDocumentTypeFilter}
      />
    </div>
  )
}
