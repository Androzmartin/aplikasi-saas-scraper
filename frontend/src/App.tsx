import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from '@/components/Layout'
import { Spinner } from '@/components/ui'
import { useAuth } from '@/context/AuthContext'
import Admin from '@/pages/Admin'
import Dashboard from '@/pages/Dashboard'
import Jobs from '@/pages/Jobs'
import LeadDetail from '@/pages/LeadDetail'
import Leads from '@/pages/Leads'
import Login from '@/pages/Login'
import Profile from '@/pages/Profile'
import ProjectDetail from '@/pages/ProjectDetail'
import Projects from '@/pages/Projects'

function RequireAuth({ children, adminOnly = false }: { children: JSX.Element; adminOnly?: boolean }) {
  const { user, loading, isAdmin } = useAuth()
  if (loading) return <div className="flex min-h-screen items-center justify-center"><Spinner /></div>
  if (!user) return <Navigate to="/login" replace />
  if (adminOnly && !isAdmin) return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:projectId" element={<ProjectDetail />} />
        <Route path="leads" element={<Leads />} />
        <Route path="leads/:leadId" element={<LeadDetail />} />
        <Route path="jobs" element={<Jobs />} />
        <Route path="profile" element={<Profile />} />
        <Route
          path="admin"
          element={
            <RequireAuth adminOnly>
              <Admin />
            </RequireAuth>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
