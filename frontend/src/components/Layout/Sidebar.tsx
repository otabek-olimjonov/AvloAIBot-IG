import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  MessageSquare,
  Ticket,
  Package,
  Tag,
  HelpCircle,
  Settings,
  Bot,
  X,
  Sparkles,
  Users,
} from 'lucide-react'
import clsx from 'clsx'
import { useAuth } from '../../contexts/AuthContext'

interface SidebarProps {
  open: boolean
  onClose: () => void
}

const operatorItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/conversations', label: 'Conversations', icon: MessageSquare },
  { to: '/tickets', label: 'Tickets', icon: Ticket },
]

const adminItems = [
  { to: '/products', label: 'Products', icon: Package },
  { to: '/promotions', label: 'Promotions', icon: Tag },
  { to: '/prompts', label: 'AI Prompts', icon: Sparkles },
  { to: '/faq', label: 'FAQ', icon: HelpCircle },
]

const configItems = [
  { to: '/settings', label: 'Settings', icon: Settings },
  { to: '/users', label: 'Users', icon: Users, adminOnly: true },
]

export default function Sidebar({ open, onClose }: SidebarProps) {
  const { isAdmin } = useAuth()

  function NavItem({ to, label, icon: Icon, end }: { to: string; label: string; icon: React.ElementType; end?: boolean }) {
    return (
      <NavLink
        to={to}
        end={end}
        onClick={() => onClose()}
        className={({ isActive }) =>
          clsx(
            'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150',
            isActive
              ? 'bg-violet-600 text-white shadow-lg shadow-violet-900/30'
              : 'text-slate-400 hover:bg-slate-800 hover:text-white',
          )
        }
      >
        <Icon className="w-[18px] h-[18px] flex-shrink-0" />
        {label}
      </NavLink>
    )
  }

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/50 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-30 w-64 bg-slate-900 flex flex-col',
          'transition-transform duration-300 ease-in-out',
          'lg:translate-x-0 lg:static lg:z-auto',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {/* Logo */}
        <div className="flex items-center justify-between h-16 px-5 border-b border-slate-800 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-violet-600 rounded-xl flex items-center justify-center">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div>
              <p className="text-white font-bold text-sm leading-none">InstaBotAdmin</p>
              <p className="text-slate-500 text-xs mt-0.5">Lavender Pillow</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden p-1.5 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-1">
          <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider px-2 mb-2">
            Main
          </p>
          {operatorItems.map((item) => (
            <NavItem key={item.to} {...item} />
          ))}

          {isAdmin && (
            <>
              <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider px-2 mt-6 mb-2">
                Catalog
              </p>
              {adminItems.map((item) => (
                <NavItem key={item.to} {...item} />
              ))}
            </>
          )}

          <p className="text-slate-500 text-xs font-semibold uppercase tracking-wider px-2 mt-6 mb-2">
            Configuration
          </p>
          {configItems
            .filter((item) => !item.adminOnly || isAdmin)
            .map((item) => (
              <NavItem key={item.to} {...item} />
            ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-slate-800 flex-shrink-0">
          <div className="bg-slate-800 rounded-xl p-3">
            <p className="text-slate-400 text-xs leading-relaxed">
              <span className="text-violet-400 font-semibold">InstaBotAdmin</span> v1.0
              <br />
              Built with AvloAI LLC
            </p>
          </div>
        </div>
      </aside>
    </>
  )
}
