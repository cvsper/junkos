import React, { createContext, useContext, useState, useEffect } from 'react'
import { authAPI } from '@/lib/api'
import { wsService } from '@/lib/websocket'

const AuthContext = createContext(null)

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState(localStorage.getItem('authToken'))

  useEffect(() => {
    if (token) {
      loadUser()
      // Connect WebSocket
      if (import.meta.env.VITE_ENABLE_WEBSOCKET === 'true') {
        wsService.connect(token)
      }
    } else {
      setLoading(false)
    }

    return () => {
      wsService.disconnect()
    }
  }, [token])

  const loadUser = async () => {
    try {
      const response = await authAPI.getCurrentUser()
      setUser(response.data)
    } catch (error) {
      console.error('Failed to load user:', error)
      logout()
    } finally {
      setLoading(false)
    }
  }

  const login = async (credentials) => {
    try {
      const response = await authAPI.login(credentials)
      const { token, user } = response.data
      localStorage.setItem('authToken', token)
      setToken(token)
      setUser(user)
      
      // Connect WebSocket
      if (import.meta.env.VITE_ENABLE_WEBSOCKET === 'true') {
        wsService.connect(token)
      }
      
      return { success: true }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.message || 'Login failed',
      }
    }
  }

  const logout = () => {
    localStorage.removeItem('authToken')
    setToken(null)
    setUser(null)
    wsService.disconnect()
  }

  const hasRole = (role) => {
    return user?.role === role
  }

  const hasPermission = (permission) => {
    const permissions = {
      admin: ['jobs:read', 'jobs:write', 'drivers:read', 'drivers:write', 'analytics:read'],
      dispatcher: ['jobs:read', 'jobs:write', 'drivers:read'],
      driver: ['jobs:read'],
    }
    return permissions[user?.role]?.includes(permission) || false
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        logout,
        hasRole,
        hasPermission,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
