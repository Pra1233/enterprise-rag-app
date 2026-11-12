import * as Tabs from '@radix-ui/react-tabs'

import { AuditLogTable } from '../components/admin/AuditLogTable'
import { UsersTable } from '../components/admin/UsersTable'

export default function AdminPage() {
  return (
    <div className="p-4 sm:p-6">
      <h1 className="mb-4 text-xl font-bold text-gray-900 dark:text-white">Admin Panel</h1>

      <Tabs.Root defaultValue="users">
        <Tabs.List className="mb-4 flex gap-1 border-b border-gray-200 dark:border-gray-700">
          <Tabs.Trigger
            value="users"
            className="border-b-2 border-transparent px-4 py-2 text-sm font-medium text-gray-500 data-[state=active]:border-brand-600 data-[state=active]:text-brand-700 dark:text-gray-400 dark:data-[state=active]:text-brand-400"
          >
            Users
          </Tabs.Trigger>
          <Tabs.Trigger
            value="audit-log"
            className="border-b-2 border-transparent px-4 py-2 text-sm font-medium text-gray-500 data-[state=active]:border-brand-600 data-[state=active]:text-brand-700 dark:text-gray-400 dark:data-[state=active]:text-brand-400"
          >
            Audit Log
          </Tabs.Trigger>
        </Tabs.List>

        <Tabs.Content value="users">
          <UsersTable />
        </Tabs.Content>
        <Tabs.Content value="audit-log">
          <AuditLogTable />
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}
