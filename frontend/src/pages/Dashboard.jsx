import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { TrendingUp, Target, Calendar, AlertCircle, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import { format } from 'date-fns'

export default function Dashboard() {
  const [picks, setPicks] = useState([])
  const [filtros, setFiltros] = useState([])
  const [rendimiento, setRendimiento] = useState(null)
  const [loading, setLoading] = useState(true)
  const today = format(new Date(), 'yyyy-MM-dd')

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      const [picksRes, filtrosRes, rendRes] = await Promise.all([
        api.getPicks(today),
        api.getFiltros(today),
        api.getRendimiento(7),
      ])
      setPicks(picksRes.picks || [])
      setFiltros(filtrosRes.filtros || [])
      setRendimiento(rendRes)
    } catch (error) {
      console.error('Error cargando dashboard:', error)
    } finally {
      setLoading(false)
    }
  }

  const directaDelDia = picks.find((p) => p.tipo_pick === 'directa')
  const combinaciones = picks.filter((p) => p.tipo_pick.startsWith('combinacion'))
  const juegosAltos = filtros.filter((f) => f.total_filtros_pasados >= 6)

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Dashboard</h1>
        <p className="text-gray-400">{format(new Date(), 'EEEE, d MMMM yyyy')}</p>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div className="card p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-gray-400 text-sm">Picks del día</p>
            <Target size={18} className="text-blue-400" />
          </div>
          <p className="text-3xl font-bold text-white">{picks.length}</p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-gray-400 text-sm">Juegos analizados</p>
            <Calendar size={18} className="text-purple-400" />
          </div>
          <p className="text-3xl font-bold text-white">{filtros.length}</p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-gray-400 text-sm">Alta confianza</p>
            <AlertCircle size={18} className="text-green-400" />
          </div>
          <p className="text-3xl font-bold text-white">{juegosAltos.length}</p>
        </div>

        <div className="card p-5">
          <div className="flex items-center justify-between mb-2">
            <p className="text-gray-400 text-sm">Efectividad 7d</p>
            <TrendingUp size={18} className="text-yellow-400" />
          </div>
          <p className="text-3xl font-bold text-white">
            {rendimiento ? `${rendimiento.efectividad}%` : '—'}
          </p>
        </div>
      </div>

      {/* Directa del día */}
      {directaDelDia && (
        <div className="card p-6 mb-6 border-2 border-green-500/30">
          <div className="flex items-center gap-2 mb-4">
            <span className="filter-badge confidence-high">⭐ Directa del día</span>
          </div>
          <div className="space-y-2">
            {directaDelDia.juegos?.map((j, i) => (
              <div key={i} className="flex justify-between items-center">
                <div>
                  <p className="text-white font-medium">{j.juego}</p>
                  <p className="text-sm text-gray-400">{j.pick}</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-green-400">{j.cuota}</p>
                  <p className="text-xs text-gray-400">{j.filtros_pasados}/10 filtros</p>
                </div>
              </div>
            ))}
          </div>
          {directaDelDia.razonamiento && (
            <p className="text-sm text-gray-300 mt-4 pt-4 border-t border-white/10">
              💡 {directaDelDia.razonamiento}
            </p>
          )}
        </div>
      )}

      {/* Top juegos */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold text-white">Top juegos del día</h2>
          <Link to="/juegos" className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1">
            Ver todos <ChevronRight size={14} />
          </Link>
        </div>
        <div className="space-y-3">
          {filtros.slice(0, 5).map((f, i) => (
            <Link
              key={i}
              to={`/juego/${f.equipo_favorecido}`}
              className="flex items-center justify-between p-3 rounded-lg bg-white/5 hover:bg-white/10 transition"
            >
              <div className="flex items-center gap-3">
                <FilterCount count={f.total_filtros_pasados} />
                <div>
                  <p className="text-white font-medium">
                    {f.equipo_favorecido} <span className="text-gray-400 mx-1">vs</span> {f.equipo_rival}
                  </p>
                  <p className="text-sm text-gray-400">{f.pick_recomendado}</p>
                </div>
              </div>
              <ChevronRight size={18} className="text-gray-500" />
            </Link>
          ))}
        </div>
      </div>

      {/* Combinaciones */}
      {combinaciones.length > 0 && (
        <div className="card p-6">
          <h2 className="text-xl font-bold text-white mb-4">Combinaciones recomendadas</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {combinaciones.map((comb, i) => (
              <div key={i} className="p-4 bg-white/5 rounded-lg">
                <p className="text-sm text-gray-400 mb-2">{comb.razonamiento}</p>
                <div className="space-y-1 mb-3">
                  {comb.juegos?.map((j, k) => (
                    <p key={k} className="text-sm text-white">
                      • {j.juego} → {j.pick}
                    </p>
                  ))}
                </div>
                {comb.cuota_total && (
                  <p className="text-lg font-bold text-yellow-400">
                    Cuota total: {comb.cuota_total}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function FilterCount({ count }) {
  let bg = 'bg-gray-500/20 text-gray-400'
  if (count >= 8) bg = 'bg-green-500/20 text-green-400'
  else if (count >= 6) bg = 'bg-yellow-500/20 text-yellow-400'
  else if (count >= 4) bg = 'bg-orange-500/20 text-orange-400'

  return (
    <div className={`w-12 h-12 rounded-lg flex items-center justify-center font-bold ${bg}`}>
      {count}/10
    </div>
  )
}
