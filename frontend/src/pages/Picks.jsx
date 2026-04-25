import { useEffect, useState } from 'react'
import { Target, TrendingUp } from 'lucide-react'
import { api } from '../lib/api'
import { format } from 'date-fns'

export default function Picks() {
  const [fecha, setFecha] = useState(format(new Date(), 'yyyy-MM-dd'))
  const [picks, setPicks] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadPicks()
  }, [fecha])

  async function loadPicks() {
    setLoading(true)
    try {
      const result = await api.getPicks(fecha)
      setPicks(result.picks || [])
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">Picks recomendados</h1>
        <input
          type="date"
          value={fecha}
          onChange={(e) => setFecha(e.target.value)}
          className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
        />
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        </div>
      ) : picks.length === 0 ? (
        <div className="card p-8 text-center">
          <Target size={48} className="text-gray-600 mx-auto mb-4" />
          <p className="text-gray-400">No hay picks para esta fecha</p>
        </div>
      ) : (
        <div className="space-y-4">
          {picks.map((pick, i) => (
            <PickCard key={i} pick={pick} />
          ))}
        </div>
      )}
    </div>
  )
}

function PickCard({ pick }) {
  const tipoLabel = {
    directa: { label: '⭐ Directa del día', color: 'border-green-500/30 bg-green-500/5' },
    combinacion_1: { label: '🎯 Combinación principal', color: 'border-yellow-500/30 bg-yellow-500/5' },
    combinacion_2: { label: '🎲 Combinación secundaria', color: 'border-orange-500/30 bg-orange-500/5' },
    colchon: { label: '🛡️ Colchón', color: 'border-blue-500/30 bg-blue-500/5' },
  }
  const info = tipoLabel[pick.tipo_pick] || { label: pick.tipo_pick, color: 'border-white/10' }
  const estadoColor = {
    pendiente: 'text-gray-400',
    ganado: 'text-green-400',
    perdido: 'text-red-400',
    push: 'text-yellow-400',
  }[pick.estado] || 'text-gray-400'

  return (
    <div className={`card p-6 border-2 ${info.color}`}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xl font-bold text-white">{info.label}</h3>
        <span className={`text-sm font-medium uppercase ${estadoColor}`}>
          {pick.estado}
        </span>
      </div>

      <div className="space-y-3">
        {pick.juegos?.map((j, i) => (
          <div key={i} className="bg-white/5 rounded-lg p-4">
            <div className="flex justify-between items-start mb-2">
              <div>
                <p className="text-white font-semibold">{j.juego}</p>
                <p className="text-sm text-blue-400">{j.pick}</p>
              </div>
              {j.cuota && (
                <div className="text-right">
                  <p className="text-2xl font-bold text-yellow-400">{j.cuota}</p>
                  {j.filtros && (
                    <p className="text-xs text-gray-400">{j.filtros}/10 filtros</p>
                  )}
                </div>
              )}
            </div>
            {j.razon && (
              <p className="text-sm text-gray-300 mt-2">💡 {j.razon}</p>
            )}
          </div>
        ))}
      </div>

      {pick.cuota_total && (
        <div className="mt-4 pt-4 border-t border-white/10 flex justify-between items-center">
          <span className="text-gray-400">Cuota total combinación:</span>
          <span className="text-2xl font-bold text-yellow-400">{pick.cuota_total}</span>
        </div>
      )}

      {pick.razonamiento && (
        <p className="text-sm text-gray-300 mt-4 pt-4 border-t border-white/10">
          {pick.razonamiento}
        </p>
      )}
    </div>
  )
}
