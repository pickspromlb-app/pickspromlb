import { useEffect, useState } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Juegos from './pages/Juegos'
import JuegoDetalle from './pages/JuegoDetalle'
import Picks from './pages/Picks'
import Historico from './pages/Historico'
import Filtros from './pages/Filtros'
import { supabase } from './lib/supabase'

function App() {
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session)
      setLoading(false)
    })

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => setSession(session)
    )

    return () => subscription.unsubscribe()
  }, [])

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center gradient-bg">
        <div className="text-center">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-400">Cargando PicksProMLB...</p>
        </div>
      </div>
    )
  }

  if (!session) {
    return <Login />
  }

  return (
    <Layout user={session.user}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/juegos" element={<Juegos />} />
        <Route path="/juego/:equipo" element={<JuegoDetalle />} />
        <Route path="/picks" element={<Picks />} />
        <Route path="/historico" element={<Historico />} />
        <Route path="/filtros" element={<Filtros />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Layout>
  )
}

export default App
