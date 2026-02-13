import React, { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'
import {
  LayoutDashboard,
  ClipboardList,
  Users,
  Calendar,
  BarChart3,
  Menu,
  X,
  LogOut,
  Truck,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, roles: ['admin', 'dispatcher'] },
  { name: 'Jobs', href: '/jobs', icon: ClipboardList, roles: ['admin', 'dispatcher'] },
  { name: 'Dispatch', href: '/dispatch', icon: Truck, roles: ['admin', 'dispatcher'] },
  { name: 'Calendar', href: '/calendar', icon: Calendar, roles: ['admin', 'dispatcher'] },
  { name: 'Drivers', href: '/drivers', icon: Users, roles: ['admin', 'dispatcher'] },
  { name: 'Analytics', href: '/analytics', icon: BarChart3, roles: ['admin'] },
]

export default function DashboardLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const filteredNavigation = navigation.filter((item) => item.roles.includes(user?.role))

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Mobile sidebar */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="fixed inset-0 bg-gray-600 bg-opacity-75" onClick={() => setSidebarOpen(false)} />
          <div className="fixed inset-y-0 left-0 flex w-64 flex-col bg-white">
            <div className="flex h-16 items-center justify-between px-4 border-b">
              <div className="flex items-center">
                <Truck className="h-8 w-8 text-primary" />
                <span className="ml-2 text-xl font-bold">Umuve</span>
              </div>
              <button onClick={() => setSidebarOpen(false)}>
                <X className="h-6 w-6" />
              </button>
            </div>
            <nav className="flex-1 space-y-1 px-2 py-4">
              {filteredNavigation.map((item) => {
                const isActive = location.pathname === item.href
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    onClick={() => setSidebarOpen(false)}
                    className={cn(
                      'flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors',
                      isActive
                        ? 'bg-primary text-white'
                        : 'text-gray-700 hover:bg-gray-100'
                    )}
                  >
                    <item.icon className="mr-3 h-5 w-5" />
                    {item.name}
                  </Link>
                )
              })}
            </nav>
            <div className="border-t p-4">
              <div className="flex items-center mb-3">
                <div className="flex-shrink-0">
                  <div className="h-10 w-10 rounded-full bg-primary flex items-center justify-center text-white font-semibold">
                    {user?.name?.charAt(0) || 'U'}
                  </div>
                </div>
                <div className="ml-3">
                  <p className="text-sm font-medium text-gray-900">{user?.name}</p>
                  <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
                </div>
              </div>
              <Button variant="outline" className="w-full" onClick={handleLogout}>
                <LogOut className="mr-2 h-4 w-4" />
                Sign Out
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        <div className="flex flex-col flex-grow bg-white border-r overflow-y-auto">
          <div className="flex items-center h-16 px-4 border-b">
            <Truck className="h-8 w-8 text-primary" />
            <span className="ml-2 text-xl font-bold">Umuve</span>
          </div>
          <nav className="flex-1 space-y-1 px-2 py-4">
            {filteredNavigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  className={cn(
                    'flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors',
                    isActive
                      ? 'bg-primary text-white'
                      : 'text-gray-700 hover:bg-gray-100'
                  )}
                >
                  <item.icon className="mr-3 h-5 w-5" />
                  {item.name}
                </Link>
              )
            })}
          </nav>
          <div className="border-t p-4">
            <div className="flex items-center mb-3">
              <div className="flex-shrink-0">
                <div className="h-10 w-10 rounded-full bg-primary flex items-center justify-center text-white font-semibold">
                  {user?.name?.charAt(0) || 'U'}
                </div>
              </div>
              <div className="ml-3">
                <p className="text-sm font-medium text-gray-900">{user?.name}</p>
                <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
              </div>
            </div>
            <Button variant="outline" className="w-full" onClick={handleLogout}>
              <LogOut className="mr-2 h-4 w-4" />
              Sign Out
            </Button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-64">
        <div className="sticky top-0 z-10 flex h-16 flex-shrink-0 bg-white border-b lg:hidden">
          <button
            type="button"
            className="px-4 text-gray-500 focus:outline-none"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-6 w-6" />
          </button>
          <div className="flex flex-1 items-center justify-between px-4">
            <div className="flex items-center">
              <Truck className="h-6 w-6 text-primary" />
              <span className="ml-2 text-lg font-bold">Umuve</span>
            </div>
          </div>
        </div>
        <main className="flex-1">
          <div className="py-6">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">{children}</div>
          </div>
        </main>
      </div>
    </div>
  )
}
