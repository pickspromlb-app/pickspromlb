import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Calendar, ChevronRight } from 'lucide-react'
import { api } from '../lib/api'
import { format } from 'date-fns'

export default function Juegos() {
  const [fecha, setFecha] = useState(format(new Date(), 'yyyy-MM-dd'))
  const [juegos, setJuegos] = useState([])
  const [filtros, setFiltros] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [fecha])

  async function loadData() {
    setLoading(true)
    try {
      const [juegosRes, filtrosRes] = await Promise.all([
        api.getJuegos(fecha),
        api.getFiltros(fecha),
      ])
      setJuegos(juegosRes.juegos || [])
      setFiltros(filtrosRes.filtros || [])
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  // Combinar juegos con sus filtros
  const juegosConAnalisis = juegos.map((j) => {
    const filtro = filtros.find(
      (f) =>
        (f.equipo_favorecido === j.equipo_local && f.equipo_rival === j.equipo_visitante) ||
        (f.equipo_favorecido === j.equipo_visitante && f.equipo_rival === j.equipo_local)
    )
    return { ...j, analisis: filtro }
  })

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">Juegos del día</h1>
        <div className="flex items-center gap-4">
          <Calendar size={18} className="text-gray-400" />
          <input
            type="date"
            value={fecha}
            onChange={(e) => setFecha(e.target.value)}
            className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
          />
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        </div>
      ) : juegos.length === 0 ? (
        <div className="card p-8 text-center">
          <p className="text-gray-400">No hay juegos para esta fecha</p>
        </div>
      ) : (
        <div className="space-y-3">
          {juegosConAnalisis
            .sort((a, b) => (b.analisis?.total_filtros_pasados || 0) - (a.analisis?.total_filtros_pasados || 0))
            .map((juego, i) => (
              <Link
                key={i}
                to={`/juego/${juego.equipo_local}`}
                className="card p-5 flex items-center justify-between hover:scale-[1.01] transition-transform"
              >
                <div className="flex items-center gap-4">
                  {juego.analisis && (
                    <FilterBadge count={juego.analisis.total_filtros_pasados} />
                  )}
                  <div>
                    <p className="text-lg font-semibold text-white">
                      {juego.equipo_visitante} @ {juego.equipo_local}
                    </p>
                    <p className="text-sm text-gray-400">
                      {juego.estadio || 'Estadio TBD'} •{' '}
                      {juego.hora_inicio
                        ? format(new Date(juego.hora_inicio), 'HH:mm')
                        : 'TBD'}
                    </p>
                    {juego.analisis?.pick_recomendado && (
                      <p className="text-sm text-blue-400 mt-1">
                        💡 {juego.analisis.pick_recomendado} ({juego.analisis.equipo_favorecido})
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  {juego.ml_local && (
                    <div className="text-right text-sm">
                      <p className="text-gray-400">
                        {juego.equipo_visitante}: {juego.ml_visitante > 0 ? '+' : ''}{juego.ml_visitante}
                      </p>
                      <p className="text-gray-400">
                        {juego.equipo_local}: {juego.ml_local > 0 ? '+' : ''}{juego.ml_local}
                      </p>
                    </div>
                  )}
                  <ChevronRight className="text-gray-500" />
                </div>
              </Link>
            ))}
        </div>
      )}
    </div>
  )
}

function FilterBadge({ count }) {
  let bg = 'bg-gray-500/20 text-gray-400'
  let label = 'NO BET'
  if (count >= 8) {
    bg = 'bg-green-500/20 text-green-400 border-green-500/30'
    label = 'DIRECTA'
  } else if (count >= 6) {
    bg = 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
    label = 'COMBI'
  } else if (count >= 4) {
    bg = 'bg-orange-500/20 text-orange-400 border-orange-500/30'
    label = 'COLCHÓN'
  }

  return (
    <div className={`flex flex-col items-center justify-center w-20 h-20 rounded-xl border-2 ${bg}`}>
      <span className="text-2xl font-bold">{count}</span>
      <span className="text-[10px] font-semibold">{label}</span>
    </div>
  )
}
