import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, Cloud, Wind, Droplets, Thermometer } from 'lucide-react'
import { api } from '../lib/api'
import { format } from 'date-fns'

export default function JuegoDetalle() {
  const { equipo } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadData()
  }, [equipo])

  async function loadData() {
    try {
      const result = await api.getJuegoPorEquipo(equipo)
      setData(result)
    } catch (error) {
      console.error('Error:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="text-center py-12">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
      </div>
    )
  }

  if (!data || !data.juego) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-400">Juego no encontrado</p>
        <Link to="/juegos" className="text-blue-400 mt-4 inline-block">← Volver</Link>
      </div>
    )
  }

  const { juego, analisis, stats_local, stats_visitante } = data

  return (
    <div>
      <Link to="/juegos" className="text-blue-400 mb-6 inline-flex items-center gap-2 hover:text-blue-300">
        <ArrowLeft size={18} /> Volver a juegos
      </Link>

      {/* Header */}
      <div className="card p-6 mb-6">
        <h1 className="text-3xl font-bold text-white mb-2">
          {juego.equipo_visitante} @ {juego.equipo_local}
        </h1>
        <p className="text-gray-400">
          {juego.estadio} •{' '}
          {juego.hora_inicio ? format(new Date(juego.hora_inicio), 'HH:mm') : 'TBD'}
        </p>
        {juego.pitcher_local && (
          <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-gray-400">Pitcher Local</p>
              <p className="text-white font-medium">{juego.pitcher_local}</p>
            </div>
            <div>
              <p className="text-gray-400">Pitcher Visitante</p>
              <p className="text-white font-medium">{juego.pitcher_visitante}</p>
            </div>
          </div>
        )}
      </div>

      {/* Análisis con filtros */}
      {analisis && (
        <div className="card p-6 mb-6">
          <h2 className="text-xl font-bold text-white mb-4">
            Análisis: {analisis.equipo_favorecido} ({analisis.total_filtros_pasados}/10 filtros)
          </h2>
          <p className="text-blue-400 mb-4">
            💡 Pick recomendado: <strong>{analisis.pick_recomendado}</strong>
          </p>

          <div className="grid grid-cols-5 sm:grid-cols-10 gap-2 mb-4">
            {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => {
              const passed = analisis[`f${i}`]
              return (
                <div
                  key={i}
                  className={`text-center p-3 rounded-lg ${
                    passed
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'bg-gray-500/20 text-gray-500 border border-gray-500/30'
                  }`}
                >
                  <p className="text-xs">F{i}</p>
                  <p className="text-lg">{passed ? '✓' : '×'}</p>
                </div>
              )
            })}
          </div>

          {analisis.alertas && analisis.alertas.length > 0 && (
            <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4 mt-4">
              <p className="text-yellow-400 font-semibold mb-2">⚠️ Alertas:</p>
              <ul className="space-y-1 text-sm text-gray-300">
                {analisis.alertas.map((a, i) => (
                  <li key={i}>• {a}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Diferenciales */}
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-5 gap-3 text-sm">
            <DiffCard label="wOBA diff" value={analisis.woba_diff} />
            <DiffCard label="wRC+ diff" value={analisis.wrc_plus_diff} />
            <DiffCard label="OPS diff" value={analisis.ops_diff} />
            <DiffCard label="wRAA diff" value={analisis.wraa_diff} />
            <DiffCard label="BB/K diff" value={analisis.bbk_diff} />
          </div>
        </div>
      )}

      {/* Stats comparadas */}
      <div className="card p-6 mb-6">
        <h2 className="text-xl font-bold text-white mb-4">Stats L5 comparadas</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-white/10">
                <th className="text-left py-2 text-gray-400">Métrica</th>
                <th className="text-right py-2 text-gray-400">{juego.equipo_visitante}</th>
                <th className="text-right py-2 text-gray-400">{juego.equipo_local}</th>
              </tr>
            </thead>
            <tbody>
              <StatRow label="AVG" v={stats_visitante?.avg_l5} l={stats_local?.avg_l5} />
              <StatRow label="OBP" v={stats_visitante?.obp_l5} l={stats_local?.obp_l5} />
              <StatRow label="SLG" v={stats_visitante?.slg_l5} l={stats_local?.slg_l5} />
              <StatRow label="OPS" v={stats_visitante?.ops_l5} l={stats_local?.ops_l5} />
              <StatRow label="ISO" v={stats_visitante?.iso_l5} l={stats_local?.iso_l5} />
              <StatRow label="BABIP" v={stats_visitante?.babip_l5} l={stats_local?.babip_l5} />
              <StatRow label="wOBA" v={stats_visitante?.woba_l5} l={stats_local?.woba_l5} />
              <StatRow label="wRC+" v={stats_visitante?.wrc_plus_l5} l={stats_local?.wrc_plus_l5} />
              <StatRow label="wRAA" v={stats_visitante?.wraa_l5} l={stats_local?.wraa_l5} />
            </tbody>
          </table>
        </div>
      </div>

      {/* Clima */}
      {juego.clima_temp_c !== null && juego.clima_temp_c !== undefined && (
        <div className="card p-6">
          <h2 className="text-xl font-bold text-white mb-4">🌤️ Clima</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <ClimaCard icon={Thermometer} label="Temperatura" value={`${juego.clima_temp_c}°C`} />
            <ClimaCard icon={Droplets} label="Humedad" value={`${juego.clima_humedad}%`} />
            <ClimaCard icon={Wind} label="Viento" value={`${juego.clima_viento_mph} mph`} />
            <ClimaCard icon={Cloud} label="Lluvia" value={`${juego.clima_lluvia_pct || 0}%`} />
          </div>
        </div>
      )}
    </div>
  )
}

function StatRow({ label, v, l }) {
  return (
    <tr className="border-b border-white/5">
      <td className="py-2 text-gray-300">{label}</td>
      <td className="py-2 text-right text-white">{v ?? '—'}</td>
      <td className="py-2 text-right text-white">{l ?? '—'}</td>
    </tr>
  )
}

function DiffCard({ label, value }) {
  const positive = parseFloat(value) > 0
  return (
    <div className="bg-white/5 rounded-lg p-3 text-center">
      <p className="text-xs text-gray-400">{label}</p>
      <p className={`text-lg font-bold ${positive ? 'text-green-400' : 'text-red-400'}`}>
        {value > 0 ? '+' : ''}{value}
      </p>
    </div>
  )
}

function ClimaCard({ icon: Icon, label, value }) {
  return (
    <div className="bg-white/5 rounded-lg p-4 text-center">
      <Icon size={24} className="text-blue-400 mx-auto mb-2" />
      <p className="text-xs text-gray-400">{label}</p>
      <p className="text-lg font-bold text-white">{value}</p>
    </div>
  )
}
