import { Routes, Route } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ui/ProtectedRoute'
import Layout from './components/Layout/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Conversations from './pages/Conversations'
import ConversationDetail from './pages/ConversationDetail'
import Tickets from './pages/Tickets'
import Products from './pages/Products'
import Promotions from './pages/Promotions'
import Prompts from './pages/Prompts'
import FAQ from './pages/FAQ'
import Settings from './pages/Settings'
import Users from './pages/Users'
import NotFound from './pages/NotFound'
import { ToastContainer } from './contexts/ToastContext'

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="conversations" element={<Conversations />} />
          <Route path="conversations/:id" element={<ConversationDetail />} />
          <Route path="tickets" element={<Tickets />} />
          <Route
            path="products"
            element={
              <ProtectedRoute requireAdmin>
                <Products />
              </ProtectedRoute>
            }
          />
          <Route
            path="promotions"
            element={
              <ProtectedRoute requireAdmin>
                <Promotions />
              </ProtectedRoute>
            }
          />
          <Route
            path="prompts"
            element={
              <ProtectedRoute requireAdmin>
                <Prompts />
              </ProtectedRoute>
            }
          />
          <Route
            path="faq"
            element={
              <ProtectedRoute requireAdmin>
                <FAQ />
              </ProtectedRoute>
            }
          />
          <Route
            path="settings"
            element={
              <ProtectedRoute requireAdmin>
                <Settings />
              </ProtectedRoute>
            }
          />
          <Route
            path="users"
            element={
              <ProtectedRoute requireAdmin>
                <Users />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
      <ToastContainer />
    </AuthProvider>
  )
}
