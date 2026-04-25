import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { api } from '../lib/api'
import { format, subDays } from 'date-fns'

export default function Historico() {
  const [dias, setDias] = useState(30)
  const [historico, setHistorico] = useState([])
  const [rendimiento, setRendimiento] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [dias])

  async function loadData() {
    setLoading(true)
    try {
      const desde = format(subDays(new Date(), dias), 'yyyy-MM-dd')
      const [histRes, rendRes] = await Promise.all([
        api.getHistorico(desde),
        api.getRendimiento(dias),
      ])
      setHistorico(histRes.picks || [])
      setRendimiento(rendRes)
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  // Agrupar por fecha para gráfica
  const datosGrafica = agruparPorFecha(historico)

  return (
    <div>
      <div className="mb-6 flex justify-between items-center">
        <h1 className="text-3xl font-bold text-white">Histórico</h1>
        <select
          value={dias}
          onChange={(e) => setDias(parseInt(e.target.value))}
          className="bg-white/5 border border-white/10 rounded-lg px-4 py-2 text-white"
        >
          <option value={7}>Últimos 7 días</option>
          <option value={14}>Últimos 14 días</option>
          <option value={30}>Últimos 30 días</option>
          <option value={90}>Últimos 90 días</option>
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
        </div>
      ) : (
        <>
          {/* Stats globales */}
          {rendimiento && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <Stat label="Total picks" value={rendimiento.total_picks} />
              <Stat label="Ganados" value={rendimiento.ganados} color="text-green-400" />
              <Stat label="Perdidos" value={rendimiento.perdidos} color="text-red-400" />
              <Stat label="Efectividad" value={`${rendimiento.efectividad}%`} color="text-yellow-400" />
            </div>
          )}

          {/* Gráfica */}
          {datosGrafica.length > 0 && (
            <div className="card p-6 mb-6">
              <h2 className="text-xl font-bold text-white mb-4">Efectividad diaria</h2>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={datosGrafica}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis dataKey="fecha" stroke="#9CA3AF" />
                  <YAxis stroke="#9CA3AF" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1f3a',
                      border: '1px solid rgba(255,255,255,0.1)',
                      borderRadius: '8px',
                    }}
                  />
                  <Line type="monotone" dataKey="efectividad" stroke="#10B981" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Tabla histórica */}
          <div className="card p-6">
            <h2 className="text-xl font-bold text-white mb-4">Detalle</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/10">
                    <th className="text-left py-3 text-gray-400">Fecha</th>
                    <th className="text-left py-3 text-gray-400">Matchup</th>
                    <th className="text-center py-3 text-gray-400">Filtros</th>
                    <th className="text-left py-3 text-gray-400">Pick</th>
                    <th className="text-center py-3 text-gray-400">Resultado</th>
                  </tr>
                </thead>
                <tbody>
                  {historico.map((h, i) => (
                    <tr key={i} className="border-b border-white/5 hover:bg-white/5">
                      <td className="py-3 text-gray-300">{h.fecha}</td>
                      <td className="py-3 text-white">
                        {h.equipo_favorecido} vs {h.equipo_rival}
                      </td>
                      <td className="py-3 text-center text-blue-400 font-medium">
                        {h.total_filtros_pasados}/10
                      </td>
                      <td className="py-3 text-gray-300">{h.pick_recomendado}</td>
                      <td className="py-3 text-center">
                        {h.resultado_pick === true && <span className="text-green-400">✓ Ganado</span>}
                        {h.resultado_pick === false && <span className="text-red-400">✗ Perdido</span>}
                        {h.resultado_pick === null && <span className="text-gray-500">Pendiente</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function Stat({ label, value, color = 'text-white' }) {
  return (
    <div className="card p-5">
      <p className="text-gray-400 text-sm mb-1">{label}</p>
      <p className={`text-3xl font-bold ${color}`}>{value}</p>
    </div>
  )
}

function agruparPorFecha(historico) {
  const grupos = {}
  for (const h of historico) {
    if (!grupos[h.fecha]) {
      grupos[h.fecha] = { fecha: h.fecha, ganados: 0, total: 0 }
    }
    if (h.resultado_pick !== null) {
      grupos[h.fecha].total++
      if (h.resultado_pick) grupos[h.fecha].ganados++
    }
  }
  return Object.values(grupos)
    .map((g) => ({
      fecha: g.fecha,
      efectividad: g.total > 0 ? Math.round((g.ganados / g.total) * 100) : 0,
    }))
    .sort((a, b) => a.fecha.localeCompare(b.fecha))
}
