import { useEffect, useState } from 'react'
import { Filter } from 'lucide-react'
import { api } from '../lib/api'

export default function Filtros() {
  const [filtros, setFiltros] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    try {
      const result = await api.getEfectividad()
      setFiltros(result.filtros || [])
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  const ordenados = [...filtros].sort((a, b) => 
    parseFloat(b.porcentaje_efectividad) - parseFloat(a.porcentaje_efectividad)
  )

  return (
    <div>
      <h1 className="text-3xl font-bold text-white mb-6">📊 Efectividad de Filtros</h1>

      {loading ? (
        <div className="text-center py-12">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        </div>
      ) : (
        <>
          {/* Top 2 - estrellas */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            {ordenados.slice(0, 2).map((f) => (
              <div key={f.filtro} className="card p-6 border-2 border-yellow-500/30 bg-yellow-500/5">
                <div className="flex items-center gap-3 mb-2">
                  <span className="text-3xl">⭐</span>
                  <h2 className="text-2xl font-bold text-white">{f.filtro}</h2>
                </div>
                <p className="text-yellow-400 text-4xl font-bold mb-2">
                  {f.porcentaje_efectividad}%
                </p>
                <p className="text-gray-300">{f.descripcion}</p>
                {f.total_casos > 0 && (
                  <p className="text-sm text-gray-400 mt-2">
                    {f.total_ganados}/{f.total_casos} casos ganados
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* Resto de filtros */}
          <div className="space-y-3">
            {ordenados.slice(2).map((f) => (
              <div key={f.filtro} className="card p-5 flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <Filter size={24} className="text-blue-400" />
                  <div>
                    <h3 className="text-lg font-bold text-white">{f.filtro}</h3>
                    <p className="text-sm text-gray-400">{f.descripcion}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-bold text-blue-400">
                    {f.porcentaje_efectividad}%
                  </p>
                  {f.total_casos > 0 && (
                    <p className="text-xs text-gray-400">
                      {f.total_ganados}/{f.total_casos}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-8 card p-6 bg-blue-500/5 border-blue-500/20">
            <h3 className="text-lg font-bold text-white mb-3">📌 Reglas de decisión</h3>
            <ul className="space-y-2 text-sm text-gray-300">
              <li>• <span className="text-green-400 font-semibold">8-10 filtros</span> → Directa del día (Moneyline)</li>
              <li>• <span className="text-yellow-400 font-semibold">6-7 filtros</span> → Combinación principal</li>
              <li>• <span className="text-orange-400 font-semibold">4-5 filtros</span> → Solo Run Line con colchón (+1.5/+2.5)</li>
              <li>• <span className="text-gray-400 font-semibold">0-3 filtros</span> → NO BET</li>
            </ul>
          </div>
        </>
      )}
    </div>
  )
}
