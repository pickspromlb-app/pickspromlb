// Cliente para consumir el API de FastAPI (Railway)
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

class ApiClient {
  async request(endpoint, options = {}) {
    const url = `${API_URL}${endpoint}`
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers,
        },
      })
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      return await response.json()
    } catch (error) {
      console.error(`API error en ${endpoint}:`, error)
      throw error
    }
  }

  // Juegos
  getJuegos(fecha) {
    const query = fecha ? `?fecha=${fecha}` : ''
    return this.request(`/api/juegos${query}`)
  }

  getJuegoPorEquipo(equipo, fecha) {
    const query = fecha ? `?fecha=${fecha}` : ''
    return this.request(`/api/juegos/${equipo}${query}`)
  }

  // Picks
  getPicks(fecha) {
    const query = fecha ? `?fecha=${fecha}` : ''
    return this.request(`/api/picks${query}`)
  }

  // Filtros
  getFiltros(fecha) {
    const query = fecha ? `?fecha=${fecha}` : ''
    return this.request(`/api/filtros${query}`)
  }

  getEfectividad() {
    return this.request('/api/efectividad')
  }

  // Rendimiento
  getRendimiento(dias = 7) {
    return this.request(`/api/rendimiento?dias=${dias}`)
  }

  getHistorico(desde, hasta) {
    const params = new URLSearchParams({ desde })
    if (hasta) params.append('hasta', hasta)
    return this.request(`/api/historico?${params.toString()}`)
  }

  // Calendario
  getCalendario(desde, hasta) {
    const params = new URLSearchParams()
    if (desde) params.append('desde', desde)
    if (hasta) params.append('hasta', hasta)
    return this.request(`/api/calendario?${params.toString()}`)
  }

  // Equipo stats
  getStatsEquipo(equipo, fecha) {
    const query = fecha ? `?fecha=${fecha}` : ''
    return this.request(`/api/equipos/${equipo}/stats${query}`)
  }

  // Trigger manual (para admin)
  triggerRecolectar() {
    return this.request('/api/trigger/recolectar', { method: 'POST' })
  }

  triggerAnalizar() {
    return this.request('/api/trigger/analizar', { method: 'POST' })
  }
}

export const api = new ApiClient()
