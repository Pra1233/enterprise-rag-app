import { UploadCloud } from 'lucide-react'
import { type ChangeEvent, type DragEvent, useId, useRef, useState } from 'react'

import { useDocumentUpload } from '../../hooks/useDocumentUpload'
import { formatFileSize } from '../../utils/formatters'
import { UploadProgress } from './UploadProgress'

// Mirrors the backend's current constraints (src/core/config.py):
// MAX_UPLOAD_SIZE_BYTES=50MB, ALLOWED_UPLOAD_EXTENSIONS=(".pdf",) only.
// DOCX/TXT are not yet accepted server-side, so we don't offer them here.
const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
const ACCEPTED_EXTENSION = '.pdf'

export function DocumentUpload() {
  const { items, uploadFile, dismissItem } = useDocumentUpload()
  const [isDragging, setIsDragging] = useState(false)
  const [validationError, setValidationError] = useState<string | null>(null)
  const inputId = useId()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const validateAndUpload = (files: FileList | null) => {
    if (!files || files.length === 0) return
    setValidationError(null)

    for (const file of Array.from(files)) {
      if (!file.name.toLowerCase().endsWith(ACCEPTED_EXTENSION)) {
        setValidationError(`"${file.name}" is not a PDF. Only PDF files are currently supported.`)
        continue
      }
      if (file.size > MAX_FILE_SIZE_BYTES) {
        setValidationError(
          `"${file.name}" (${formatFileSize(file.size)}) exceeds the ${formatFileSize(MAX_FILE_SIZE_BYTES)} limit.`,
        )
        continue
      }
      void uploadFile(file)
    }
  }

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    validateAndUpload(e.dataTransfer.files)
  }

  const handleFileInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    validateAndUpload(e.target.files)
    e.target.value = ''
  }

  return (
    <div className="flex flex-col gap-3">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors ${
          isDragging
            ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
            : 'border-gray-300 dark:border-gray-700'
        }`}
      >
        <UploadCloud className="size-8 text-gray-400" aria-hidden="true" />
        <p className="text-sm text-gray-600 dark:text-gray-300">
          Drag and drop a PDF here, or{' '}
          <label htmlFor={inputId} className="cursor-pointer font-medium text-brand-600 hover:underline">
            browse
          </label>
        </p>
        <p className="text-xs text-gray-400">PDF only, up to {formatFileSize(MAX_FILE_SIZE_BYTES)}</p>
        <input
          ref={fileInputRef}
          id={inputId}
          type="file"
          accept={ACCEPTED_EXTENSION}
          multiple
          className="sr-only"
          onChange={handleFileInputChange}
        />
      </div>

      {validationError && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {validationError}
        </p>
      )}

      <UploadProgress items={items} onDismiss={dismissItem} />
    </div>
  )
}
