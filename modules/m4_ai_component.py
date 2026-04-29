"""
modules/m4_ai_component.py
M4 · AI Component — Anomaly Detector

Detecta bloques cuyo tiempo de llegada es estadísticamente anómalo.
Modelo: Isolation Forest (scikit-learn), entrenado sobre datos reales de Bitcoin.
Baseline de comparación: método estadístico por z-score.

Justificación del modelo:
- Los tiempos inter-bloque siguen una distribución exponencial (proceso de Poisson).
- No existe ground truth de qué bloques son "anómalos" → problema no supervisado.
- Isolation Forest es robusto ante distribuciones no gaussianas como la exponencial.
- Deviaciones pueden indicar caídas de hash rate o comportamiento de mining pools.
"""

import requests
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
import streamlit as st

BASE_URL          = "https://blockstream.info/api"
TARGET_BLOCK_TIME = 600  # segundos


# ── Datos ─────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def fetch_blocks(n: int = 200) -> pd.DataFrame:
    """Obtiene los últimos N bloques y calcula tiempos inter-bloque."""
    blocks = []
    r = requests.get(f"{BASE_URL}/blocks", timeout=10)
    r.raise_for_status()
    blocks.extend(r.json())

    while len(blocks) < n:
        oldest = blocks[-1]["height"] - 1
        r = requests.get(f"{BASE_URL}/blocks/{oldest}", timeout=10)
        r.raise_for_status()
        page = r.json()
        if not page:
            break
        blocks.extend(page)

    df = pd.DataFrame(blocks[:n])
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df = df.sort_values("height").reset_index(drop=True)

    # Feature principal: tiempo entre bloques consecutivos (segundos)
    df["ibt"] = df["timestamp"].diff()

    # Features derivadas para el modelo
    df["log_ibt"] = np.log1p(df["ibt"])                        # comprime la cola exponencial
    df["ibt_z"]   = (df["ibt"] - TARGET_BLOCK_TIME) / TARGET_BLOCK_TIME  # desviación relativa al target

    return df.dropna(subset=["ibt"]).reset_index(drop=True)


# ── Modelo ────────────────────────────────────────────────────────────────────

def run_isolation_forest(df: pd.DataFrame, contamination: float) -> pd.DataFrame:
    """
    Entrena Isolation Forest sobre tres features:
    - ibt       : tiempo bruto en segundos
    - log_ibt   : log del tiempo (estabiliza la escala de la exponencial)
    - ibt_z     : desviación relativa respecto al target de 600 s

    Devuelve el DataFrame con columnas anomaly (bool) y anomaly_score (float).
    El score es la función de decisión: más negativo = más anómalo.
    """
    X_raw = df[["ibt", "log_ibt", "ibt_z"]].values
    X     = StandardScaler().fit_transform(X_raw)

    model = IsolationForest(
        contamination=contamination,
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X)

    df = df.copy()
    df["anomaly"]       = model.predict(X) == -1   # -1 = anómalo, 1 = normal
    df["anomaly_score"] = model.decision_function(X)
    return df


def run_statistical_baseline(df: pd.DataFrame) -> pd.DataFrame:
    """
    Baseline estadístico: z-score sobre la distribución exponencial.
    Para Exp(λ): media = 1/λ, std = 1/λ → usamos la media muestral.
    Umbral: ibt > media + 3*std  o  ibt < media - 2*std
    """
    mu  = df["ibt"].mean()
    std = df["ibt"].std()
    df  = df.copy()
    df["stat_anomaly"] = (df["ibt"] > mu + 3 * std) | (df["ibt"] < mu - 2 * std)
    return df


def compute_metrics(df: pd.DataFrame) -> dict:
    """
    Métricas de evaluación del modelo.
    Como no hay ground truth, usamos:
    - Tasa de anomalías detectadas
    - Acuerdo con el baseline estadístico (proxy de precisión)
    - Score medio de anomalías vs normales (separabilidad)
    """
    n_total   = len(df)
    n_if      = df["anomaly"].sum()
    n_stat    = df["stat_anomaly"].sum()
    agreement = (df["anomaly"] == df["stat_anomaly"]).mean()

    score_anom   = df.loc[df["anomaly"],  "anomaly_score"].mean()
    score_normal = df.loc[~df["anomaly"], "anomaly_score"].mean()

    # Verdaderos positivos: IF y estadístico coinciden en anómalo
    tp = (df["anomaly"] & df["stat_anomaly"]).sum()
    precision_proxy = tp / n_if if n_if > 0 else 0

    return {
        "n_total":        n_total,
        "n_if":           n_if,
        "n_stat":         n_stat,
        "agreement":      agreement,
        "score_anom":     score_anom,
        "score_normal":   score_normal,
        "precision_proxy": precision_proxy,
    }


# ── Render ────────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M4 · AI Component — Anomaly Detector")
    st.caption(
        "Detección de anomalías en tiempos inter-bloque usando **Isolation Forest**. "
        "Baseline comparativo: z-score sobre distribución exponencial."
    )

    # ── Explicación del modelo ────────────────────────────────────────────────
    with st.expander("ℹ️ Justificación del modelo", expanded=False):
        st.markdown("""
**¿Por qué Isolation Forest?**

Los tiempos inter-bloque de Bitcoin siguen una **distribución exponencial** con λ = 1/600 s
(proceso de Poisson: cada intento de hash es independiente con probabilidad de éxito muy baja).

El problema de detección de anomalías aquí es **no supervisado** — no existe un dataset etiquetado
de bloques "anómalos". Isolation Forest es adecuado porque:

1. No asume distribución gaussiana (funciona bien con exponenciales).
2. Aísla outliers construyendo árboles de decisión aleatorios — los puntos anómalos
   se aíslan con menos particiones.
3. Es robusto ante la cola larga de la distribución exponencial.

**Features usadas:**
- `ibt`: tiempo inter-bloque en segundos (feature principal)
- `log_ibt`: logaritmo del tiempo (comprime la cola, estabiliza la escala)
- `ibt_z`: desviación relativa respecto al target de 600 s

**Evaluación:** sin ground truth, usamos el **acuerdo con el baseline estadístico** (z-score)
como proxy de precisión, y el **anomaly score** como medida de confianza.

**Interpretación de anomalías:** bloques con tiempos muy largos pueden indicar caída del
hash rate de la red; bloques muy rápidos en serie pueden indicar comportamiento de mining pools
con ventaja de propagación.
        """)

    col1, col2 = st.columns(2)
    n_blocks      = col1.slider("Bloques a analizar", 50, 300, 150, step=25)
    contamination = col2.slider(
        "Tasa de contaminación esperada",
        0.01, 0.15, 0.05, step=0.01,
        help="Fracción de bloques que el modelo considera anómalos a priori."
    )

    if st.button("🤖 Ejecutar detector", key="m4_run"):
        st.cache_data.clear()

    with st.spinner("Cargando bloques y entrenando modelo..."):
        try:
            df_raw = fetch_blocks(n_blocks)
            df     = run_isolation_forest(df_raw, contamination)
            df     = run_statistical_baseline(df)
            m      = compute_metrics(df)
        except Exception as e:
            st.error(f"Error: {e}")
            return

    # ── Métricas ──────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Bloques analizados",       m["n_total"])
    col2.metric("Anomalías (Isolation Forest)", m["n_if"],
                delta=f"{m['n_if']/m['n_total']*100:.1f}%")
    col3.metric("Anomalías (baseline estadístico)", m["n_stat"])
    col4.metric("Acuerdo IF vs estadístico", f"{m['agreement']*100:.1f}%")

    st.divider()

    # ── Gráfico 1: Serie temporal con anomalías ───────────────────────────────
    st.subheader("Tiempos inter-bloque — anomalías detectadas")
    st.caption("Azul = normal · Rojo = anomalía (Isolation Forest) · Cruz naranja = anomalía estadística")

    df_n = df[~df["anomaly"]]
    df_a = df[df["anomaly"]]
    df_s = df[df["stat_anomaly"]]

    fig_ts = go.Figure()
    fig_ts.add_trace(go.Scatter(
        x=df_n["datetime"], y=df_n["ibt"],
        mode="markers", name="Normal",
        marker=dict(color="#1565c0", size=5, opacity=0.55),
    ))
    fig_ts.add_trace(go.Scatter(
        x=df_a["datetime"], y=df_a["ibt"],
        mode="markers", name="Anomalía (IF)",
        marker=dict(color="#e53935", size=9, symbol="circle"),
    ))
    fig_ts.add_trace(go.Scatter(
        x=df_s["datetime"], y=df_s["ibt"],
        mode="markers", name="Anomalía (estadístico)",
        marker=dict(color="#ff6d00", size=11, symbol="x", opacity=0.8),
    ))
    fig_ts.add_hline(
        y=TARGET_BLOCK_TIME, line_dash="dash", line_color="#43a047",
        annotation_text="Target 600 s", annotation_position="top right",
    )
    fig_ts.update_layout(
        xaxis_title="Fecha (UTC)", yaxis_title="Tiempo inter-bloque (s)",
        height=380, legend=dict(x=0.01, y=0.99),
    )
    st.plotly_chart(fig_ts, use_container_width=True)

    st.divider()

    # ── Gráfico 2: Distribución + exponencial teórica ─────────────────────────
    st.subheader("Distribución real vs exponencial teórica (λ = 1/600)")
    st.markdown(
        "Si los tiempos siguen la exponencial teórica, la red funciona con normalidad. "
        "Los bloques anómalos aparecen en rojo — generalmente en las colas de la distribución."
    )

    fig_dist = go.Figure()
    fig_dist.add_trace(go.Histogram(
        x=df_n["ibt"], nbinsx=40, name="Normal",
        marker_color="#1565c0", opacity=0.65, histnorm="probability density",
    ))
    if not df_a.empty:
        fig_dist.add_trace(go.Histogram(
            x=df_a["ibt"], nbinsx=20, name="Anomalía (IF)",
            marker_color="#e53935", opacity=0.75, histnorm="probability density",
        ))

    x_range = np.linspace(0, df["ibt"].quantile(0.99), 300)
    lam = 1 / TARGET_BLOCK_TIME
    fig_dist.add_trace(go.Scatter(
        x=x_range, y=lam * np.exp(-lam * x_range),
        mode="lines", name="Exp. teórica (λ=1/600)",
        line=dict(color="#ff6d00", dash="dash", width=2),
    ))
    fig_dist.update_layout(
        xaxis_title="Tiempo inter-bloque (s)", yaxis_title="Densidad de probabilidad",
        barmode="overlay", height=340,
    )
    st.plotly_chart(fig_dist, use_container_width=True)

    st.divider()

    # ── Gráfico 3: Anomaly score ───────────────────────────────────────────────
    st.subheader("Anomaly score por bloque")
    st.caption("Más negativo = más anómalo. Puntos por debajo de 0 son clasificados como anomalías.")

    fig_score = go.Figure(go.Scatter(
        x=df["datetime"], y=df["anomaly_score"],
        mode="markers",
        marker=dict(
            color=["#e53935" if a else "#1565c0" for a in df["anomaly"]],
            size=5, opacity=0.7,
        ),
        name="Anomaly score",
    ))
    fig_score.add_hline(y=0, line_dash="dash", line_color="#212121",
                        annotation_text="Umbral de anomalía")
    fig_score.update_layout(
        xaxis_title="Fecha (UTC)", yaxis_title="Anomaly score", height=280,
    )
    st.plotly_chart(fig_score, use_container_width=True)

    st.divider()

    # ── Evaluación ────────────────────────────────────────────────────────────
    st.subheader("Evaluación del modelo")

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.markdown("**Métricas:**")
        st.markdown(f"- Bloques analizados: **{m['n_total']}**")
        st.markdown(f"- Anomalías IF: **{m['n_if']}** ({m['n_if']/m['n_total']*100:.1f}%)")
        st.markdown(f"- Anomalías estadístico (baseline): **{m['n_stat']}**")
        st.markdown(f"- Acuerdo IF ↔ estadístico: **{m['agreement']*100:.1f}%**")
        st.markdown(f"- Precisión proxy (TP/IF): **{m['precision_proxy']*100:.1f}%**")
        st.markdown(f"- Score medio anomalías: **{m['score_anom']:.4f}**")
        st.markdown(f"- Score medio normales: **{m['score_normal']:.4f}**")

    with col_e2:
        st.markdown("**Interpretación:**")
        st.markdown(
            "- El **acuerdo** entre IF y el baseline estadístico valida que el modelo "
            "no etiqueta bloques arbitrariamente.\n"
            "- La **diferencia de scores** entre anomalías y normales mide la separabilidad "
            "del modelo — cuanto mayor, mejor discrimina.\n"
            "- La **precisión proxy** indica qué fracción de las anomalías IF "
            "también son detectadas por el método estadístico.\n"
            "- Limitación: sin ground truth real, estas métricas son indicativas, no definitivas."
        )

    # Tabla de anomalías
    with st.expander(f"Ver {m['n_if']} bloques anómalos detectados"):
        cols_show = ["height", "datetime", "ibt", "anomaly_score", "stat_anomaly"]
        st.dataframe(
            df[df["anomaly"]][cols_show]
            .rename(columns={
                "height":        "Altura",
                "datetime":      "Fecha (UTC)",
                "ibt":           "Δt (s)",
                "anomaly_score": "Score IF",
                "stat_anomaly":  "Anómalo (estadístico)",
            })
            .sort_values("Score IF"),
            use_container_width=True,
        )