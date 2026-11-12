import { ChevronDown, FileText } from 'lucide-react'
import { useState } from 'react'

import type { ChatCitation } from '../../types/chat.types'

function fileNameFromUri(sourceUri: string): string {
  const parts = sourceUri.split('/')
  return parts[parts.length - 1] || sourceUri
}

/**
 * NOTE: the backend's Citation schema (src/api/schemas/chat.py) only returns
 * document_id, chunk_id, source_uri and score — no page number and no source
 * excerpt. Rather than inventing those fields, this component shows exactly
 * what the API provides and labels the rest as unavailable.
 */
export function SourceCitations({ citations }: { citations: ChatCitation[] }) {
  const [expanded, setExpanded] = useState(false)

  if (citations.length === 0) return null

  return (
    <div className="mt-2 border-t border-gray-100 pt-2 dark:border-gray-700">
      <button
        type="button"
        onClick={() => setExpanded((e) => !e)}
        aria-expanded={expanded}
        className="flex items-center gap-1 text-xs font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
      >
        <ChevronDown className={`size-3.5 transition-transform ${expanded ? 'rotate-180' : ''}`} />
        {citations.length} source{citations.length === 1 ? '' : 's'}
      </button>

      {expanded && (
        <ul className="mt-2 flex flex-col gap-1.5">
          {citations.map((citation, index) => (
            <li
              key={citation.chunk_id}
              className="flex items-start gap-2 rounded-md bg-gray-50 p-2 text-xs text-gray-600 dark:bg-gray-800 dark:text-gray-300"
            >
              <FileText className="mt-0.5 size-3.5 shrink-0 text-gray-400" />
              <div className="min-w-0">
                <p className="truncate font-medium text-gray-700 dark:text-gray-200">
                  [{index + 1}] {fileNameFromUri(citation.source_uri)}
                </p>
                <p className="text-gray-400">
                  chunk {citation.chunk_id.slice(0, 8)} · relevance {citation.score.toFixed(2)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
