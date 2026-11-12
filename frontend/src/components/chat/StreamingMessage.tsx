import ReactMarkdown from 'react-markdown'

import type { ChatMessage } from '../../types/chat.types'
import { TypingIndicator } from './TypingIndicator'

export function StreamingMessage({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl bg-gray-100 px-4 py-2.5 text-sm text-gray-800 dark:bg-gray-800 dark:text-gray-100">
        {message.content ? (
          <div className="markdown-content">
            <ReactMarkdown>{message.content}</ReactMarkdown>
            <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse bg-gray-400 align-middle" />
          </div>
        ) : (
          <TypingIndicator />
        )}
      </div>
    </div>
  )
}
