import { DocumentList } from '../components/documents/DocumentList'
import { DocumentUpload } from '../components/documents/DocumentUpload'

export default function DocumentsPage() {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8 p-6">
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">Upload</h2>
        <DocumentUpload />
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-400">Library</h2>
        <DocumentList />
      </section>
    </div>
  )
}
