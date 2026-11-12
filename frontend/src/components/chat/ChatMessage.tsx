import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'

import type { ChatMessage as ChatMessageType } from '../../types/chat.types'
import { SourceCitations } from './SourceCitations'
import { StreamingMessage } from './StreamingMessage'

interface ChatMessageProps {
  message: ChatMessageType
}

export function ChatMessageBubble({ message }: ChatMessageProps) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  if (!isUser && (message.status === 'pending' || message.status === 'streaming')) {
    return <StreamingMessage message={message} />
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard API can be unavailable (e.g. insecure context) — fail silently, no crash.
    }
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`group relative max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
          isUser
            ? 'bg-brand-600 text-white'
            : message.status === 'error'
              ? 'border border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300'
              : 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-100'
        }`}
      >
        {message.status === 'error' ? (
          <p>{message.errorMessage}</p>
        ) : isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <>
            <div className="markdown-content">
              <ReactMarkdown
                components={{
                  code(props) {
                    const { className, children } = props
                    const match = /language-(\w+)/.exec(className ?? '')
                    return match ? (
                      <SyntaxHighlighter style={oneDark} language={match[1]} PreTag="div">
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    ) : (
                      <code className={className}>{children}</code>
                    )
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
            {message.citations && <SourceCitations citations={message.citations} />}
          </>
        )}

        {!isUser && message.status === 'done' && message.content && (
          <button
            type="button"
            onClick={handleCopy}
            aria-label="Copy response"
            className="absolute -bottom-3 right-2 rounded-md border border-gray-200 bg-white p-1 text-gray-400 opacity-0 shadow-sm transition-opacity group-hover:opacity-100 hover:text-gray-600 dark:border-gray-600 dark:bg-gray-700"
          >
            {copied ? <Check className="size-3" /> : <Copy className="size-3" />}
          </button>
        )}
      </div>
    </div>
  )
}
