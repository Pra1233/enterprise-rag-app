import { Send, Square } from 'lucide-react'
import { type KeyboardEvent, useState } from 'react'

interface ChatInputProps {
  onSend: (text: string) => void
  onStop: () => void
  isStreaming: boolean
  documentTypeFilter: string
  onDocumentTypeFilterChange: (value: string) => void
}

const DOCUMENT_TYPE_OPTIONS = ['', 'pdf', 'docx', 'txt', 'markdown', 'html']

export function ChatInput({
  onSend,
  onStop,
  isStreaming,
  documentTypeFilter,
  onDocumentTypeFilterChange,
}: ChatInputProps) {
  const [value, setValue] = useState('')

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || isStreaming) return
    onSend(trimmed)
    setValue('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <div className="border-t border-gray-200 bg-white p-3 dark:border-gray-700 dark:bg-gray-900">
      <div className="mb-2 flex items-center gap-2">
        <label htmlFor="doc-type-filter" className="text-xs text-gray-400">
          Filter:
        </label>
        <select
          id="doc-type-filter"
          value={documentTypeFilter}
          onChange={(e) => onDocumentTypeFilterChange(e.target.value)}
          className="rounded-md border border-gray-200 bg-white px-2 py-1 text-xs text-gray-600 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
        >
          <option value="">All document types</option>
          {DOCUMENT_TYPE_OPTIONS.filter(Boolean).map((opt) => (
            <option key={opt} value={opt}>
              {opt.toUpperCase()}
            </option>
          ))}
        </select>
      </div>

      <div className="flex items-end gap-2">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder="Ask a question about your documents… (Enter to send, Shift+Enter for a new line)"
          rows={1}
          className="max-h-40 min-h-11 flex-1 resize-y rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-800 outline-none focus:border-brand-500 disabled:bg-gray-50 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:disabled:bg-gray-900"
        />

        {isStreaming ? (
          <button
            type="button"
            onClick={onStop}
            aria-label="Stop generating"
            className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-gray-800 text-white hover:bg-gray-900"
          >
            <Square className="size-4" fill="currentColor" />
          </button>
        ) : (
          <button
            type="button"
            onClick={submit}
            disabled={!value.trim()}
            aria-label="Send message"
            className="flex size-11 shrink-0 items-center justify-center rounded-lg bg-brand-600 text-white hover:bg-brand-700 disabled:bg-brand-300"
          >
            <Send className="size-4" />
          </button>
        )}
      </div>
    </div>
  )
}
