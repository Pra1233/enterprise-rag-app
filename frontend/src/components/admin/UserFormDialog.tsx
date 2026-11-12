import * as Dialog from '@radix-ui/react-dialog'
import * as Label from '@radix-ui/react-label'
import * as Select from '@radix-ui/react-select'
import * as Switch from '@radix-ui/react-switch'
import { Check, ChevronDown, X } from 'lucide-react'
import { type FormEvent, useEffect, useState } from 'react'

import type { AdminUser, CreateUserPayload, UpdateUserPayload } from '../../types/admin.types'
import type { UserRole } from '../../types/auth.types'
import { Button } from '../common/Button'

interface UserFormDialogProps {
  isOpen: boolean
  onClose: () => void
  /** undefined = create mode, provided = edit mode */
  user?: AdminUser
  onCreate: (payload: CreateUserPayload) => Promise<unknown>
  onUpdate: (userId: string, payload: UpdateUserPayload) => Promise<unknown>
  isSubmitting: boolean
}

const inputClass =
  'w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30 dark:border-gray-700 dark:bg-gray-900 dark:text-white'

export function UserFormDialog({ isOpen, onClose, user, onCreate, onUpdate, isSubmitting }: UserFormDialogProps) {
  const isEditMode = Boolean(user)

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<UserRole>('user')
  const [llmLimit, setLlmLimit] = useState(200)
  const [uploadLimit, setUploadLimit] = useState(20)
  const [isActive, setIsActive] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!isOpen) return
    setError(null)
    if (user) {
      setUsername(user.username)
      setRole(user.role)
      setLlmLimit(user.llm_request_limit)
      setUploadLimit(user.upload_limit)
      setIsActive(user.is_active)
    } else {
      setUsername('')
      setPassword('')
      setRole('user')
      setLlmLimit(200)
      setUploadLimit(20)
      setIsActive(true)
    }
  }, [isOpen, user])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      if (isEditMode && user) {
        await onUpdate(user.id, {
          role,
          llm_request_limit: llmLimit,
          upload_limit: uploadLimit,
          is_active: isActive,
        })
      } else {
        await onCreate({
          username,
          password,
          role,
          llm_request_limit: llmLimit,
          upload_limit: uploadLimit,
        })
      }
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    }
  }

  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40 data-[state=open]:animate-in data-[state=open]:fade-in" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl bg-white p-6 shadow-xl dark:bg-gray-800">
          <div className="mb-4 flex items-center justify-between">
            <Dialog.Title className="text-lg font-semibold text-gray-900 dark:text-gray-100">
              {isEditMode ? `Edit ${user?.username}` : 'Create user'}
            </Dialog.Title>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close dialog"
                className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-700"
              >
                <X className="size-5" />
              </button>
            </Dialog.Close>
          </div>

          <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
            {!isEditMode && (
              <>
                <div>
                  <Label.Root htmlFor="new-username" className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">
                    Username
                  </Label.Root>
                  <input
                    id="new-username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    minLength={3}
                    className={inputClass}
                  />
                </div>
                <div>
                  <Label.Root htmlFor="new-password" className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">
                    Password
                  </Label.Root>
                  <input
                    id="new-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                    className={inputClass}
                  />
                </div>
              </>
            )}

            <div>
              <Label.Root className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">Role</Label.Root>
              <Select.Root value={role} onValueChange={(v) => setRole(v as UserRole)}>
                <Select.Trigger className={`${inputClass} flex items-center justify-between`}>
                  <Select.Value />
                  <Select.Icon>
                    <ChevronDown className="size-4" />
                  </Select.Icon>
                </Select.Trigger>
                <Select.Portal>
                  <Select.Content className="z-[60] overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-800">
                    <Select.Viewport className="p-1">
                      {(['user', 'admin'] as const).map((r) => (
                        <Select.Item
                          key={r}
                          value={r}
                          className="flex cursor-pointer items-center justify-between rounded-md px-3 py-2 text-sm text-gray-700 outline-none hover:bg-gray-100 data-[state=checked]:text-brand-700 dark:text-gray-200 dark:hover:bg-gray-700"
                        >
                          <Select.ItemText>{r === 'admin' ? 'Admin' : 'User'}</Select.ItemText>
                          <Select.ItemIndicator>
                            <Check className="size-4" />
                          </Select.ItemIndicator>
                        </Select.Item>
                      ))}
                    </Select.Viewport>
                  </Select.Content>
                </Select.Portal>
              </Select.Root>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label.Root htmlFor="llm-limit" className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">
                  LLM request limit
                </Label.Root>
                <input
                  id="llm-limit"
                  type="number"
                  min={0}
                  value={llmLimit}
                  onChange={(e) => setLlmLimit(Number(e.target.value))}
                  className={inputClass}
                />
              </div>
              <div>
                <Label.Root htmlFor="upload-limit" className="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-200">
                  Upload limit
                </Label.Root>
                <input
                  id="upload-limit"
                  type="number"
                  min={0}
                  value={uploadLimit}
                  onChange={(e) => setUploadLimit(Number(e.target.value))}
                  className={inputClass}
                />
              </div>
            </div>

            {isEditMode && (
              <div className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2 dark:border-gray-700">
                <Label.Root htmlFor="is-active" className="text-sm font-medium text-gray-700 dark:text-gray-200">
                  Account active
                </Label.Root>
                <Switch.Root
                  id="is-active"
                  checked={isActive}
                  onCheckedChange={setIsActive}
                  className="relative h-6 w-11 rounded-full bg-gray-300 outline-none data-[state=checked]:bg-brand-600 dark:bg-gray-600"
                >
                  <Switch.Thumb className="block size-5 translate-x-0.5 rounded-full bg-white transition-transform will-change-transform data-[state=checked]:translate-x-[22px]" />
                </Switch.Root>
              </div>
            )}

            {error && (
              <p role="alert" className="text-sm text-red-600 dark:text-red-400">
                {error}
              </p>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button type="button" variant="secondary" onClick={onClose}>
                Cancel
              </Button>
              <Button type="submit" isLoading={isSubmitting}>
                {isEditMode ? 'Save changes' : 'Create user'}
              </Button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
