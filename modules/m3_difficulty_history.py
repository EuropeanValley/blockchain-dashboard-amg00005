"""
modules/m3_difficulty_history.py
M3 · Difficulty History

Evolución de la dificultad de Bitcoin por períodos de ajuste (2016 bloques).
Usa únicamente Blockstream API.
"""

import requests
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BASE_URL          = "https://blockstream.info/api"
BLOCKS_PER_PERIOD = 2016
TARGET_BLOCK_TIME = 600
TARGET_PERIOD     = BLOCKS_PER_PERIOD * TARGET_BLOCK_TIME  # 1_209_600 s


# ── Datos ─────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=600)
def fetch_difficulty_history(n_periods: int = 20) -> pd.DataFrame:
    """
    Recorre los últimos N períodos de ajuste.
    Solo hace 2 llamadas por período (bloque inicio + bloque inicio anterior).
    """
    tip_height = int(requests.get(f"{BASE_URL}/blocks/tip/height", timeout=10).text)
    current_start = (tip_height // BLOCKS_PER_PERIOD) * BLOCKS_PER_PERIOD

    records = []
    # Precargamos los hashes y datos de cada período de una sola vez
    for i in range(n_periods + 1):
        height = current_start - i * BLOCKS_PER_PERIOD
        if height < 0:
            break

        bh = requests.get(f"{BASE_URL}/block-height/{height}", timeout=10).text.strip()
        block = requests.get(f"{BASE_URL}/block/{bh}", timeout=10).json()
        records.append({
            "height":     height,
            "timestamp":  block["timestamp"],
            "difficulty": block["difficulty"],
        })

    # Necesitamos n+1 bloques para calcular n tiempos entre períodos
    df = pd.DataFrame(records).sort_values("height").reset_index(drop=True)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)

    # Tiempo real entre períodos consecutivos
    df["period_time_s"] = df["timestamp"].diff()
    df["avg_block_s"]   = df["period_time_s"] / BLOCKS_PER_PERIOD
    df["time_ratio"]    = df["avg_block_s"] / TARGET_BLOCK_TIME

    # Variación de dificultad
    df["diff_change_pct"] = df["difficulty"].pct_change() * 100

    # Descartamos la primera fila (no tiene período anterior)
    return df.iloc[1:].reset_index(drop=True)


@st.cache_data(ttl=120)
def fetch_current_period() -> dict:
    """Estado del período de ajuste en curso."""
    tip_height = int(requests.get(f"{BASE_URL}/blocks/tip/height", timeout=10).text)
    period_start = (tip_height // BLOCKS_PER_PERIOD) * BLOCKS_PER_PERIOD
    blocks_done  = tip_height - period_start

    bh    = requests.get(f"{BASE_URL}/block-height/{period_start}", timeout=10).text.strip()
    block = requests.get(f"{BASE_URL}/block/{bh}", timeout=10).json()

    tip_block = requests.get(f"{BASE_URL}/blocks", timeout=10).json()[0]
    elapsed   = tip_block["timestamp"] - block["timestamp"]
    avg_so_far = elapsed / blocks_done if blocks_done > 0 else TARGET_BLOCK_TIME

    projected_pct = (avg_so_far * BLOCKS_PER_PERIOD / TARGET_PERIOD - 1) * 100

    return {
        "tip_height":      tip_height,
        "period_start":    period_start,
        "blocks_done":     blocks_done,
        "blocks_left":     BLOCKS_PER_PERIOD - blocks_done,
        "avg_so_far":      avg_so_far,
        "difficulty":      block["difficulty"],
        "projected_pct":   projected_pct,
    }


# ── Render ────────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M3 · Difficulty History")
    st.caption("Evolución de la dificultad de Bitcoin por períodos de ajuste (2016 bloques ≈ 2 semanas)")

    n_periods = st.slider("Períodos de ajuste a mostrar", 5, 25, 12, step=1)
    st.caption(f"⚠️ Cada período requiere 2 llamadas a la API — {n_periods} períodos = ~{n_periods*2} llamadas.")

    if st.button("📊 Cargar historial", key="m3_load"):
        st.cache_data.clear()

    with st.spinner(f"Cargando {n_periods} períodos de ajuste..."):
        try:
            df      = fetch_difficulty_history(n_periods)
            current = fetch_current_period()
        except Exception as e:
            st.error(f"Error al obtener datos: {e}")
            return

    # ── Métricas período actual ───────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Dificultad actual", f"{current['difficulty']/1e12:.2f} T")
    col2.metric("Bloques en el período", f"{current['blocks_done']} / {BLOCKS_PER_PERIOD}")
    col3.metric("Tiempo medio actual", f"{current['avg_so_far']:.0f} s")
    col4.metric(
        "Próximo ajuste estimado",
        f"{current['projected_pct']:+.2f}%",
        delta="sube" if current["projected_pct"] > 0 else "baja",
        delta_color="inverse",
    )
    st.caption(
        f"Altura actual: {current['tip_height']:,} — "
        f"período iniciado en bloque {current['period_start']:,} — "
        f"faltan {current['blocks_left']} bloques para el próximo ajuste."
    )

    st.divider()

    # ── Gráfico 1: Dificultad ─────────────────────────────────────────────────
    st.subheader("Evolución de la dificultad")
    st.markdown(
        "Cada punto marca el inicio de un período de ajuste. "
        "Los triángulos rojos indican períodos donde la dificultad bajó."
    )

    fig_diff = go.Figure()
    fig_diff.add_trace(go.Scatter(
        x=df["datetime"], y=df["difficulty"] / 1e12,
        mode="lines+markers", name="Dificultad (T)",
        line=dict(color="#1565c0", width=2),
        marker=dict(size=6, color="#1565c0"),
    ))

    df_neg = df[df["diff_change_pct"] < 0]
    if not df_neg.empty:
        fig_diff.add_trace(go.Scatter(
            x=df_neg["datetime"], y=df_neg["difficulty"] / 1e12,
            mode="markers", name="Ajuste negativo",
            marker=dict(color="#e53935", size=10, symbol="triangle-down"),
        ))

    for _, row in df.iterrows():
        fig_diff.add_vline(
            x=row["datetime"], line_width=1,
            line_dash="dot", line_color="rgba(120,120,120,0.25)",
        )

    fig_diff.update_layout(
        xaxis_title="Fecha (UTC)", yaxis_title="Dificultad (Terahashes)",
        height=370, legend=dict(x=0.01, y=0.99),
    )
    st.plotly_chart(fig_diff, use_container_width=True)

    st.divider()

    # ── Gráfico 2: Ratio tiempo real / objetivo ───────────────────────────────
    st.subheader("Ratio tiempo real / objetivo (600 s por bloque)")
    st.markdown(
        "**Verde (ratio < 1):** bloques más rápidos → dificultad subirá.  \n"
        "**Rojo (ratio > 1):** bloques más lentos → dificultad bajará.  \n"
        "Fórmula: `nueva_dificultad = vieja × (tiempo_real / 1_209_600)`"
    )

    df_r = df.dropna(subset=["time_ratio"])
    colors_r = ["#e53935" if r > 1 else "#43a047" for r in df_r["time_ratio"]]

    fig_ratio = go.Figure(go.Bar(
        x=df_r["datetime"], y=df_r["time_ratio"],
        marker_color=colors_r, opacity=0.85,
    ))
    fig_ratio.add_hline(
        y=1.0, line_dash="dash", line_color="#212121",
        annotation_text="Objetivo (ratio = 1)", annotation_position="top right",
    )
    fig_ratio.update_layout(
        xaxis_title="Período", yaxis_title="t_real / 600 s", height=300,
    )
    st.plotly_chart(fig_ratio, use_container_width=True)

    st.divider()

    # ── Gráfico 3: Variación porcentual ───────────────────────────────────────
    st.subheader("Variación porcentual de dificultad por ajuste")

    df_c = df.dropna(subset=["diff_change_pct"])
    colors_c = ["#e53935" if v < 0 else "#1565c0" for v in df_c["diff_change_pct"]]

    fig_chg = go.Figure(go.Bar(
        x=df_c["datetime"], y=df_c["diff_change_pct"],
        marker_color=colors_c,
    ))
    fig_chg.add_hline(y=0, line_color="#212121", line_width=1)
    fig_chg.update_layout(
        xaxis_title="Período", yaxis_title="Cambio (%)", height=280,
    )
    st.plotly_chart(fig_chg, use_container_width=True)

    with st.expander("Ver tabla de períodos"):
        st.dataframe(
            df[["height", "datetime", "difficulty", "avg_block_s", "time_ratio", "diff_change_pct"]]
            .rename(columns={
                "height":         "Altura inicio",
                "datetime":       "Fecha",
                "difficulty":     "Dificultad",
                "avg_block_s":    "Tiempo medio (s)",
                "time_ratio":     "Ratio t/600",
                "diff_change_pct":"Cambio (%)",
            }),
            use_container_width=True,
        )