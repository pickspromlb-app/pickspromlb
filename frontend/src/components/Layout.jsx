import { Link, useLocation } from 'react-router-dom'
import { Home, Calendar, Target, History, Filter, LogOut, User } from 'lucide-react'
import { logout } from '../lib/supabase'

const NAV_ITEMS = [
  { path: '/', label: 'Dashboard', icon: Home },
  { path: '/juegos', label: 'Juegos', icon: Calendar },
  { path: '/picks', label: 'Picks del día', icon: Target },
  { path: '/filtros', label: 'Filtros', icon: Filter },
  { path: '/historico', label: 'Histórico', icon: History },
]

export default function Layout({ children, user }) {
  const location = useLocation()

  return (
    <div className="min-h-screen gradient-bg flex">
      {/* Sidebar */}
      <aside className="w-64 bg-black/30 border-r border-white/10 p-6">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">⚾ PicksProMLB</h1>
          <p className="text-xs text-gray-400 mt-1">Análisis Sabermétrico</p>
        </div>

        <nav className="space-y-2">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.path
            const Icon = item.icon
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                    : 'text-gray-300 hover:bg-white/5 hover:text-white'
                }`}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </Link>
            )
          })}
        </nav>

        {/* User card */}
        <div className="mt-auto pt-6 border-t border-white/10 absolute bottom-6 left-6 right-6 w-52">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center">
              {user?.user_metadata?.avatar_url ? (
                <img src={user.user_metadata.avatar_url} alt="" className="w-full h-full rounded-full" />
              ) : (
                <User size={18} className="text-blue-400" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">
                {user?.email?.split('@')[0]}
              </p>
              <p className="text-xs text-gray-400 truncate">{user?.email}</p>
            </div>
          </div>
          <button
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition text-sm"
          >
            <LogOut size={14} />
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-8 max-w-7xl mx-auto">{children}</div>
      </main>
    </div>
  )
}
