import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../../context/AuthContext'
import { Loader } from '../common/Loader'

export function AdminRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader label="Checking your session…" size="lg" />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  if (user.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
