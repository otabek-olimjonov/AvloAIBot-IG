import { Link } from 'react-router-dom'
import { Bot, Home } from 'lucide-react'

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex flex-col items-center justify-center text-center px-4">
      <div className="w-20 h-20 rounded-3xl bg-violet-100 flex items-center justify-center mb-6">
        <Bot className="w-10 h-10 text-violet-500" />
      </div>
      <h1 className="text-6xl font-bold text-slate-200 mb-2">404</h1>
      <h2 className="text-xl font-semibold text-slate-700 mb-2">Page not found</h2>
      <p className="text-slate-500 mb-8 max-w-sm">
        The page you're looking for doesn't exist or has been moved.
      </p>
      <Link
        to="/"
        className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-5 py-2.5 rounded-xl font-medium transition-colors"
      >
        <Home className="w-4 h-4" /> Back to Dashboard
      </Link>
    </div>
  )
}
