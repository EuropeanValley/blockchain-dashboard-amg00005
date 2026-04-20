"""
modules/m1_pow_monitor.py
M1 · Proof of Work Monitor

Muestra el estado actual del mining de Bitcoin:
- Dificultad actual y su representación como threshold de ceros
- Distribución de tiempos entre bloques (últimos N bloques)
- Hash rate estimado de la red
"""

import time
import requests
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

BASE_URL = "https://blockstream.info/api"


# ── Funciones de acceso a la API ─────────────────────────────────────────────

def fetch_latest_blocks(n: int = 50) -> list[dict]:
    """
    Devuelve los últimos N bloques con sus metadatos.
    Blockstream devuelve bloques de 10 en 10 por página.
    """
    blocks = []
    # El endpoint /blocks devuelve los 10 más recientes
    # Para conseguir más, pasamos el height del último bloque recibido
    response = requests.get(f"{BASE_URL}/blocks", timeout=10)
    response.raise_for_status()
    page = response.json()
    blocks.extend(page)

    while len(blocks) < n:
        # Pedimos la siguiente página desde el bloque más antiguo que tenemos
        oldest_height = blocks[-1]["height"] - 1
        response = requests.get(f"{BASE_URL}/blocks/{oldest_height}", timeout=10)
        response.raise_for_status()
        page = response.json()
        if not page:
            break
        blocks.extend(page)

    return blocks[:n]


def bits_to_target_hex(bits: int) -> str:
    """
    Convierte el campo 'bits' del header al target completo en hexadecimal.
    Formato compacto: bits = 0xAABBCCDD
      - AA = exponente (número de bytes del target)
      - BBCCDD = coeficiente (los 3 bytes más significativos)
    target = coeficiente * 256^(exponente - 3)
    """
    exponent = bits >> 24          # byte más significativo
    coefficient = bits & 0xFFFFFF  # 3 bytes restantes
    target = coefficient * (256 ** (exponent - 3))
    # Formateamos como hex de 64 caracteres (256 bits)
    return f"{target:064x}"


def count_leading_zero_bits(block_hash: str) -> int:
    """Cuenta los bits cero iniciales de un hash en hexadecimal."""
    # Convertimos hex → entero y contamos desde el bit más significativo
    value = int(block_hash, 16)
    if value == 0:
        return 256
    return 256 - value.bit_length()


def estimate_hashrate(difficulty: float) -> float:
    """
    Estima el hash rate de la red en hashes/segundo.
    Fórmula: hashrate = difficulty * 2^32 / 600
    Viene de: en 600 s se espera encontrar 1 bloque,
    y la dificultad define cuántos hashes hacen falta estadísticamente.
    """
    return difficulty * (2 ** 32) / 600


# ── Render principal ──────────────────────────────────────────────────────────

def render() -> None:
    st.header("M1 · Proof of Work Monitor")
    st.caption("Estado en tiempo real del mining de Bitcoin (Blockstream API)")

    n_blocks = st.slider("Número de bloques a analizar", 10, 150, 50, step=10)

    if st.button("🔄 Actualizar datos", key="m1_refresh"):
        st.cache_data.clear()

    with st.spinner("Conectando con la red Bitcoin..."):
        try:
            blocks = _load_blocks(n_blocks)
        except Exception as e:
            st.error(f"Error al conectar con la API: {e}")
            return

    latest = blocks[0]
    df = _blocks_to_dataframe(blocks)

    # ── Fila de métricas principales ─────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    difficulty = latest.get("difficulty", 0)
    hashrate_hs = estimate_hashrate(difficulty)
    hashrate_eh = hashrate_hs / 1e18  # Exahashes/s

    col1.metric("Altura del bloque", f"{latest['height']:,}")
    col2.metric("Dificultad", f"{difficulty / 1e12:.2f} T")
    col3.metric("Hash rate estimado", f"{hashrate_eh:.2f} EH/s")
    col4.metric("Transacciones (último bloque)", f"{latest.get('tx_count', '?'):,}")

    st.divider()

    # ── Sección 1: Análisis del hash y el target ──────────────────────────────
    st.subheader("🔐 Proof of Work — Hash vs Target")

    block_hash = latest["id"]
    bits = latest.get("bits", 0)
    target_hex = bits_to_target_hex(bits)
    leading_zero_bits = count_leading_zero_bits(block_hash)
    leading_zero_hex = len(block_hash) - len(block_hash.lstrip("0"))

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Hash del último bloque:**")
        # Resaltamos los ceros iniciales en verde
        zeros_part = block_hash[:leading_zero_hex]
        rest_part = block_hash[leading_zero_hex:]
        st.markdown(
            f'<code style="font-size:0.75em">'
            f'<span style="color:#00c853;font-weight:bold">{zeros_part}</span>'
            f'{rest_part}</code>',
            unsafe_allow_html=True,
        )
        st.caption(
            f"✅ {leading_zero_hex} ceros hex iniciales = {leading_zero_bits} bits de trabajo demostrado"
        )

    with col_b:
        st.markdown("**Target (decodificado de `bits`):**")
        zeros_t = len(target_hex) - len(target_hex.lstrip("0"))
        rest_t = target_hex[zeros_t:]
        st.markdown(
            f'<code style="font-size:0.75em">'
            f'<span style="color:#ff6d00">{target_hex[:zeros_t]}</span>'
            f'{rest_t}</code>',
            unsafe_allow_html=True,
        )
        st.caption(
            "El hash del bloque debe ser MENOR que este valor (Proof of Work)"
        )

    st.info(
        f"**Bits field:** `0x{bits:08x}` → Target con {zeros_t} ceros hex. "
        f"El hash tiene {leading_zero_hex} ceros hex, por lo que "
        f"{'✅ cumple' if leading_zero_hex >= zeros_t else '❌ no cumple'} el Proof of Work."
    )

    st.divider()

    # ── Sección 2: Distribución de tiempos entre bloques ─────────────────────
    st.subheader("⏱️ Distribución de tiempos entre bloques")
    st.markdown(
        "Se espera una **distribución exponencial** (proceso de Poisson con λ = 1/600 s), "
        "porque el mining es un proceso de Bernoulli con probabilidad de éxito muy baja "
        "e independiente en cada intento."
    )

    inter_block_times = df["inter_block_time"].dropna()
    mean_time = inter_block_times.mean()
    median_time = inter_block_times.median()

    col1, col2, col3 = st.columns(3)
    col1.metric("Tiempo medio entre bloques", f"{mean_time:.0f} s ({mean_time/60:.1f} min)")
    col2.metric("Mediana", f"{median_time:.0f} s")
    col3.metric("Target teórico", "600 s (10 min)")

    # Histograma + curva exponencial teórica
    fig_hist = go.Figure()

    fig_hist.add_trace(go.Histogram(
        x=inter_block_times,
        nbinsx=30,
        name="Tiempos reales",
        marker_color="#1565c0",
        opacity=0.75,
        histnorm="probability density",
    ))

    # Curva exponencial teórica (λ = 1/600)
    x_range = np.linspace(0, inter_block_times.quantile(0.99), 200)
    lambda_teorico = 1 / 600
    y_exp = lambda_teorico * np.exp(-lambda_teorico * x_range)

    fig_hist.add_trace(go.Scatter(
        x=x_range,
        y=y_exp,
        mode="lines",
        name="Exp. teórica (λ=1/600s)",
        line=dict(color="#e53935", width=2, dash="dash"),
    ))

    fig_hist.update_layout(
        title=f"Distribución de tiempos entre bloques (últimos {n_blocks} bloques)",
        xaxis_title="Tiempo entre bloques (segundos)",
        yaxis_title="Densidad de probabilidad",
        legend=dict(x=0.6, y=0.95),
        height=400,
    )
    st.plotly_chart(fig_hist, use_container_width=True)

    st.divider()

    # ── Sección 3: Hash rate estimado ─────────────────────────────────────────
    st.subheader("⚡ Hash Rate estimado de la red")
    st.markdown(
        r"Fórmula: $\text{hashrate} = \dfrac{\text{difficulty} \times 2^{32}}{600}$ "
        "— derivada de la definición de dificultad: un minero con ese hashrate "
        "encontraría un bloque cada 600 s en promedio."
    )

    # Evolución de la dificultad a lo largo de los bloques analizados
    fig_hr = go.Figure()
    fig_hr.add_trace(go.Scatter(
        x=df["timestamp"],
        y=df["hashrate_eh"],
        mode="lines+markers",
        name="Hash rate (EH/s)",
        line=dict(color="#43a047", width=2),
        marker=dict(size=4),
    ))
    fig_hr.update_layout(
        title="Hash Rate estimado por bloque",
        xaxis_title="Fecha/hora (UTC)",
        yaxis_title="Hash rate (EH/s)",
        height=350,
    )
    st.plotly_chart(fig_hr, use_container_width=True)

    # Tabla resumen
    with st.expander("📋 Ver tabla de bloques"):
        st.dataframe(
            df[["height", "timestamp", "inter_block_time", "tx_count", "difficulty", "hashrate_eh"]]
            .rename(columns={
                "height": "Altura",
                "timestamp": "Timestamp",
                "inter_block_time": "Δt (s)",
                "tx_count": "Transacciones",
                "difficulty": "Dificultad",
                "hashrate_eh": "Hash rate (EH/s)",
            }),
            use_container_width=True,
        )


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def _load_blocks(n: int) -> list[dict]:
    """Carga bloques con cache de 60 segundos para no saturar la API."""
    return fetch_latest_blocks(n)


def _blocks_to_dataframe(blocks: list[dict]) -> pd.DataFrame:
    """Convierte la lista de bloques a un DataFrame con columnas derivadas."""
    df = pd.DataFrame(blocks)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df = df.sort_values("height").reset_index(drop=True)

    # Tiempo entre bloques consecutivos (en segundos)
    df["inter_block_time"] = df["timestamp"].diff().dt.total_seconds()

    # Hash rate estimado por bloque
    df["hashrate_eh"] = df["difficulty"].apply(
        lambda d: estimate_hashrate(d) / 1e18
    )
    return df
