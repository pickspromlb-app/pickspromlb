-- =========================================
-- PICKSPROMLB - SCHEMA DE BASE DE DATOS
-- =========================================
-- Ejecutar este script completo en Supabase SQL Editor
-- Crea todas las tablas necesarias para el sistema

-- =========================================
-- TABLA 1: equipos_diario
-- Una fila por equipo por día con sus stats por ventanas
-- =========================================
CREATE TABLE IF NOT EXISTS equipos_diario (
    id BIGSERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    equipo VARCHAR(10) NOT NULL,
    rival VARCHAR(10),
    es_local BOOLEAN,
    
    -- Stats temporada completa
    pa_temp INTEGER,
    avg_temp DECIMAL(5,3),
    obp_temp DECIMAL(5,3),
    slg_temp DECIMAL(5,3),
    ops_temp DECIMAL(5,3),
    iso_temp DECIMAL(5,3),
    babip_temp DECIMAL(5,3),
    woba_temp DECIMAL(5,3),
    wrc_plus_temp INTEGER,
    wraa_temp DECIMAL(6,2),
    bb_pct_temp DECIMAL(5,2),
    k_pct_temp DECIMAL(5,2),
    bbk_temp DECIMAL(4,2),
    
    -- Stats últimos 10 juegos
    ops_l10 DECIMAL(5,3),
    iso_l10 DECIMAL(5,3),
    babip_l10 DECIMAL(5,3),
    wraa_l10 DECIMAL(6,2),
    woba_l10 DECIMAL(5,3),
    wrc_plus_l10 INTEGER,
    
    -- Stats últimos 7 juegos
    ops_l7 DECIMAL(5,3),
    iso_l7 DECIMAL(5,3),
    babip_l7 DECIMAL(5,3),
    wraa_l7 DECIMAL(6,2),
    woba_l7 DECIMAL(5,3),
    wrc_plus_l7 INTEGER,
    
    -- Stats últimos 5 juegos (los más importantes para filtros)
    avg_l5 DECIMAL(5,3),
    obp_l5 DECIMAL(5,3),
    slg_l5 DECIMAL(5,3),
    ops_l5 DECIMAL(5,3),
    iso_l5 DECIMAL(5,3),
    babip_l5 DECIMAL(5,3),
    wraa_l5 DECIMAL(6,2),
    woba_l5 DECIMAL(5,3),
    wrc_plus_l5 INTEGER,
    bb_pct_l5 DECIMAL(5,2),
    k_pct_l5 DECIMAL(5,2),
    bbk_l5 DECIMAL(4,2),
    
    -- Stats últimos 3 juegos
    ops_l3 DECIMAL(5,3),
    iso_l3 DECIMAL(5,3),
    babip_l3 DECIMAL(5,3),
    wraa_l3 DECIMAL(6,2),
    woba_l3 DECIMAL(5,3),
    wrc_plus_l3 INTEGER,
    
    -- Stats último juego
    ops_l1 DECIMAL(5,3),
    iso_l1 DECIMAL(5,3),
    babip_l1 DECIMAL(5,3),
    wraa_l1 DECIMAL(6,2),
    woba_l1 DECIMAL(5,3),
    wrc_plus_l1 INTEGER,
    
    -- Resultado del día (se llena después del juego)
    carreras_hechas INTEGER,
    carreras_recibidas INTEGER,
    gano BOOLEAN,
    jugo_en_coors BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(fecha, equipo)
);

CREATE INDEX idx_equipos_diario_fecha ON equipos_diario(fecha);
CREATE INDEX idx_equipos_diario_equipo ON equipos_diario(equipo);

-- =========================================
-- TABLA 2: bullpenes_diario
-- Stats del bullpen de cada equipo en últimos 5 juegos
-- =========================================
CREATE TABLE IF NOT EXISTS bullpenes_diario (
    id BIGSERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    equipo VARCHAR(10) NOT NULL,
    
    ip_l5 DECIMAL(5,1),
    tbf_l5 INTEGER,
    k_9_l5 DECIMAL(4,1),
    bb_9_l5 DECIMAL(4,1),
    k_bb_l5 DECIMAL(4,2),
    hr_9_l5 DECIMAL(4,1),
    k_pct_l5 DECIMAL(5,2),
    bb_pct_l5 DECIMAL(5,2),
    k_bb_diff_pct_l5 DECIMAL(5,2),
    avg_permitido_l5 DECIMAL(5,3),
    whip_l5 DECIMAL(4,2),
    babip_permitido_l5 DECIMAL(5,3),
    lob_pct_l5 DECIMAL(5,2),
    fip_l5 DECIMAL(4,2),
    xfip_l5 DECIMAL(4,2),
    era_l5 DECIMAL(4,2),
    h_l5 INTEGER,
    hr_permitidos_l5 INTEGER,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(fecha, equipo)
);

CREATE INDEX idx_bullpenes_fecha ON bullpenes_diario(fecha);

-- =========================================
-- TABLA 3: juegos
-- Información completa de cada juego del día
-- =========================================
CREATE TABLE IF NOT EXISTS juegos (
    id BIGSERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    game_id VARCHAR(50),
    
    equipo_local VARCHAR(10) NOT NULL,
    equipo_visitante VARCHAR(10) NOT NULL,
    estadio VARCHAR(100),
    hora_inicio TIMESTAMPTZ,
    
    -- Pitchers probables
    pitcher_local VARCHAR(100),
    pitcher_visitante VARCHAR(100),
    pitcher_local_era DECIMAL(4,2),
    pitcher_visitante_era DECIMAL(4,2),
    pitcher_local_whip DECIMAL(4,2),
    pitcher_visitante_whip DECIMAL(4,2),
    
    -- Mercado
    total_runs DECIMAL(3,1),
    ml_local INTEGER,
    ml_visitante INTEGER,
    rl_local DECIMAL(3,1),
    rl_visitante DECIMAL(3,1),
    rl_local_odds INTEGER,
    rl_visitante_odds INTEGER,
    
    -- Movimiento de línea (opcional, varios snapshots)
    odds_snapshot JSONB,
    
    -- Clima
    clima_temp_f DECIMAL(4,1),
    clima_temp_c DECIMAL(4,1),
    clima_humedad INTEGER,
    clima_viento_mph DECIMAL(4,1),
    clima_viento_direccion VARCHAR(20),
    clima_lluvia_pct INTEGER,
    
    -- Resultado
    resultado_local INTEGER,
    resultado_visitante INTEGER,
    total_carreras INTEGER,
    ganador VARCHAR(10),
    
    estado VARCHAR(20) DEFAULT 'programado', -- programado, en_curso, finalizado, suspendido
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(fecha, equipo_local, equipo_visitante)
);

CREATE INDEX idx_juegos_fecha ON juegos(fecha);
CREATE INDEX idx_juegos_estado ON juegos(estado);

-- =========================================
-- TABLA 4: filtros_aplicados
-- Auditoría de qué filtros pasó cada equipo cada día
-- =========================================
CREATE TABLE IF NOT EXISTS filtros_aplicados (
    id BIGSERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    juego_id BIGINT REFERENCES juegos(id),
    
    equipo_favorecido VARCHAR(10) NOT NULL,
    equipo_rival VARCHAR(10) NOT NULL,
    
    -- Cada filtro (true/false)
    f1 BOOLEAN DEFAULT FALSE,
    f2 BOOLEAN DEFAULT FALSE,
    f3 BOOLEAN DEFAULT FALSE,
    f4 BOOLEAN DEFAULT FALSE,
    f5 BOOLEAN DEFAULT FALSE,
    f6 BOOLEAN DEFAULT FALSE,
    f7 BOOLEAN DEFAULT FALSE,
    f8 BOOLEAN DEFAULT FALSE,
    f9 BOOLEAN DEFAULT FALSE,
    f10 BOOLEAN DEFAULT FALSE,
    
    total_filtros_pasados INTEGER DEFAULT 0,
    
    -- Diferenciales calculados
    woba_diff DECIMAL(5,3),
    wrc_plus_diff INTEGER,
    ops_diff DECIMAL(5,3),
    wraa_diff DECIMAL(6,2),
    bbk_diff DECIMAL(4,2),
    
    -- Alertas detectadas
    alertas JSONB,
    rebote_tecnico_rival BOOLEAN DEFAULT FALSE,
    rival_zona_caliente BOOLEAN DEFAULT FALSE,
    
    -- Pick recomendado
    pick_recomendado VARCHAR(50),
    mercado_recomendado VARCHAR(50),
    cuota_recomendada DECIMAL(4,2),
    nivel_confianza VARCHAR(20), -- alta, media, baja, no_bet
    
    -- Resultado del pick
    resultado_pick BOOLEAN, -- true=ganó, false=perdió, null=pendiente
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(fecha, equipo_favorecido, equipo_rival)
);

CREATE INDEX idx_filtros_fecha ON filtros_aplicados(fecha);
CREATE INDEX idx_filtros_total ON filtros_aplicados(total_filtros_pasados);

-- =========================================
-- TABLA 5: historico_metricas
-- Los "698 equipos" del tipster: rangos históricos
-- =========================================
CREATE TABLE IF NOT EXISTS historico_metricas (
    id BIGSERIAL PRIMARY KEY,
    metrica VARCHAR(50) NOT NULL, -- avg, obp, slg, ops, iso, babip, woba, wrc_plus, wraa
    rango_min DECIMAL(8,3),
    rango_max DECIMAL(8,3),
    rango_descripcion VARCHAR(100), -- ej: "AVG < 0.150 (rebote técnico)"
    
    total_casos INTEGER DEFAULT 0,
    casos_2_o_menos_carreras INTEGER DEFAULT 0,
    casos_3_o_mas_carreras INTEGER DEFAULT 0,
    casos_5_o_mas_carreras INTEGER DEFAULT 0,
    casos_gano INTEGER DEFAULT 0,
    
    porcentaje_3_o_mas DECIMAL(5,2),
    porcentaje_5_o_mas DECIMAL(5,2),
    porcentaje_gano DECIMAL(5,2),
    
    es_zona_rebote BOOLEAN DEFAULT FALSE,
    es_zona_caliente BOOLEAN DEFAULT FALSE,
    
    actualizado TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(metrica, rango_min, rango_max)
);

CREATE INDEX idx_historico_metrica ON historico_metricas(metrica);

-- =========================================
-- TABLA 6: efectividad_filtros
-- Historial de efectividad de cada filtro (auto-actualizable)
-- =========================================
CREATE TABLE IF NOT EXISTS efectividad_filtros (
    id BIGSERIAL PRIMARY KEY,
    filtro VARCHAR(10) NOT NULL, -- F1, F2, ..., F10
    descripcion TEXT,
    
    total_casos INTEGER DEFAULT 0,
    total_ganados INTEGER DEFAULT 0,
    porcentaje_efectividad DECIMAL(5,2),
    
    -- Última actualización
    fecha_ultima_actualizacion DATE,
    
    UNIQUE(filtro)
);

-- Insertar los 10 filtros base
INSERT INTO efectividad_filtros (filtro, descripcion, porcentaje_efectividad) VALUES
('F1', 'wOBA diff >=0.040 + wRC+ diff >=30', 79.07),
('F2', 'OPS diff >=0.150 + wRC+ diff >=30', 81.25),
('F3', 'wRC+ diff >=30 + wRAA diff >9', 80.00),
('F4', 'wOBA diff >=0.040 + OPS diff >=0.150', 81.59),
('F5', 'wRC+ >=50 + wRAA >12 + wOBA >=0.070', 94.44),
('F6', 'wRC+ >=30 + wRAA >9 + wOBA >=0.040', 83.33),
('F7', 'wRC+ >=30 + wRAA >9 + OPS >=0.150', 83.33),
('F8', 'wRC+ >=30 + wOBA >=0.040 + OPS >=0.150', 82.05),
('F9', 'wRC+ >=30 + wRAA >9 + BB/K >=0.2', 90.00),
('F10', 'wRC+ >=40 + wRAA >9 + wOBA >=0.060', 82.10)
ON CONFLICT (filtro) DO NOTHING;

-- =========================================
-- TABLA 7: picks_diarios
-- Picks recomendados por el sistema cada día
-- =========================================
CREATE TABLE IF NOT EXISTS picks_diarios (
    id BIGSERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    
    tipo_pick VARCHAR(50) NOT NULL, -- directa, combinacion_1, combinacion_2, colchon
    
    juegos JSONB, -- array con todos los juegos de la combinación
    cuota_total DECIMAL(6,2),
    razonamiento TEXT,
    
    estado VARCHAR(20) DEFAULT 'pendiente', -- pendiente, ganado, perdido, push
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_picks_fecha ON picks_diarios(fecha);

-- =========================================
-- TABLA 8: log_ejecuciones
-- Auditoría de cuándo corrió el sistema
-- =========================================
CREATE TABLE IF NOT EXISTS log_ejecuciones (
    id BIGSERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    tipo VARCHAR(50) NOT NULL, -- recolector_manana, listin, actualizacion, resultados
    estado VARCHAR(20), -- exito, error, parcial
    mensaje TEXT,
    duracion_segundos INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_log_fecha ON log_ejecuciones(fecha);

-- =========================================
-- VIEWS ÚTILES
-- =========================================

-- View: resumen de picks del día actual
CREATE OR REPLACE VIEW v_picks_hoy AS
SELECT 
    f.fecha,
    f.equipo_favorecido,
    f.equipo_rival,
    f.total_filtros_pasados,
    f.pick_recomendado,
    f.mercado_recomendado,
    f.cuota_recomendada,
    f.nivel_confianza,
    j.hora_inicio,
    j.total_runs,
    j.ml_local,
    j.ml_visitante,
    f.alertas,
    f.resultado_pick
FROM filtros_aplicados f
LEFT JOIN juegos j ON f.juego_id = j.id
WHERE f.fecha = CURRENT_DATE
ORDER BY f.total_filtros_pasados DESC;

-- View: efectividad acumulada del sistema
CREATE OR REPLACE VIEW v_rendimiento_sistema AS
SELECT 
    fecha,
    COUNT(*) as total_picks,
    COUNT(CASE WHEN resultado_pick = true THEN 1 END) as ganados,
    COUNT(CASE WHEN resultado_pick = false THEN 1 END) as perdidos,
    ROUND(
        COUNT(CASE WHEN resultado_pick = true THEN 1 END)::numeric / 
        NULLIF(COUNT(CASE WHEN resultado_pick IS NOT NULL THEN 1 END), 0) * 100, 
        2
    ) as porcentaje_efectividad
FROM filtros_aplicados
WHERE pick_recomendado IS NOT NULL
GROUP BY fecha
ORDER BY fecha DESC;

-- =========================================
-- TRIGGERS para actualizar updated_at
-- =========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_equipos_diario_updated_at 
    BEFORE UPDATE ON equipos_diario 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_juegos_updated_at 
    BEFORE UPDATE ON juegos 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =========================================
-- POLÍTICAS DE SEGURIDAD (Row Level Security)
-- =========================================
-- Por ahora dejamos las tablas accesibles solo con service_role key
-- Si quieres habilitar RLS para el frontend, descomenta:

-- ALTER TABLE equipos_diario ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE juegos ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE filtros_aplicados ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE picks_diarios ENABLE ROW LEVEL SECURITY;

-- Mensaje final
DO $$
BEGIN
    RAISE NOTICE '✅ Schema de PicksProMLB creado exitosamente';
    RAISE NOTICE '   - 8 tablas creadas';
    RAISE NOTICE '   - 2 vistas creadas';
    RAISE NOTICE '   - 10 filtros pre-cargados';
END $$;
