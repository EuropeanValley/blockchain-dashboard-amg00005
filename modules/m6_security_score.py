"""
modules/m6_security_score.py
M6 · Security Score

Estima el coste en USD/hora de un ataque del 51% sobre Bitcoin
basándose en el hash rate actual de la red.

Referencias:
- Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System. §11
- Precio de hardware: Antminer S21 Pro (~$2,400, 234 TH/s, 3,510 W)
- Precio de electricidad: media industrial global ~$0.05/kWh
"""

import requests
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BASE_URL = "https://blockstream.info/api"

# ── Constantes de hardware (Antminer S21 Pro, referencia 2024-2025) ──────────
MINER_HASHRATE_THS  = 234        # TH/s por unidad
MINER_POWER_W       = 3_510      # vatios por unidad
MINER_PRICE_USD     = 2_400      # precio por unidad
ELECTRICITY_KWH_USD = 0.05       # USD por kWh (media industrial)


# ── Datos ─────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def fetch_network_hashrate() -> dict:
    """
    Estima el hash rate actual de la red desde el último bloque.
    Fórmula: hashrate = difficulty × 2^32 / 600
    """
    r = requests.get(f"{BASE_URL}/blocks", timeout=10)
    r.raise_for_status()
    latest = r.json()[0]

    difficulty   = latest["difficulty"]
    hashrate_hs  = difficulty * (2 ** 32) / 600   # hashes/s
    hashrate_ehs = hashrate_hs / 1e18              # EH/s
    hashrate_ths = hashrate_hs / 1e12              # TH/s

    return {
        "difficulty":   difficulty,
        "hashrate_hs":  hashrate_hs,
        "hashrate_ehs": hashrate_ehs,
        "hashrate_ths": hashrate_ths,
        "block_height": latest["height"],
    }


def compute_attack_cost(hashrate_ths: float, electricity_usd: float, miner_price: float) -> dict:
    """
    Calcula el coste de un ataque del 51%:

    El atacante necesita superar el 50% del hash rate total de la red.
    target_ths = hashrate_red × 0.51

    Coste de hardware:
      unidades = ceil(target_ths / hashrate_por_miner)
      coste_hw = unidades × precio_por_miner

    Coste operativo por hora:
      potencia_total_kw = unidades × potencia_w / 1000
      coste_elec_hora   = potencia_total_kw × electricity_usd

    Coste total por hora (amortizando hardware en 18 meses):
      amortizacion_hora = coste_hw / (18 × 30 × 24)
      coste_total_hora  = coste_elec_hora + amortizacion_hora
    """
    target_ths = hashrate_ths * 0.51
    units      = int(np.ceil(target_ths / MINER_HASHRATE_THS))

    hw_cost_usd     = units * miner_price
    power_kw        = units * MINER_POWER_W / 1000
    elec_cost_hour  = power_kw * electricity_usd
    amort_hour      = hw_cost_usd / (18 * 30 * 24)   # amortización 18 meses
    total_cost_hour = elec_cost_hour + amort_hour

    return {
        "target_ths":       target_ths,
        "units":            units,
        "hw_cost_usd":      hw_cost_usd,
        "power_kw":         power_kw,
        "elec_cost_hour":   elec_cost_hour,
        "amort_hour":       amort_hour,
        "total_cost_hour":  total_cost_hour,
    }


def nakamoto_attack_probability(q: float, z: int) -> float:
    """
    Probabilidad de que un atacante con fracción q del hash rate
    alcance la cadena honesta desde z bloques de atrás.

    Fórmula de Nakamoto (2008), §11:
      P(z, q) = 1 - sum_{k=0}^{z} [e^{-λ} × λ^k / k!] × (1 - (q/p)^{z-k})
    donde λ = z × q/p

    Simplificación práctica usada aquí:
      Si q < 0.5: P ≈ (q/p)^z  (decae exponencialmente con z)
      Si q >= 0.5: P = 1 (atacante siempre gana eventualmente)
    """
    p = 1 - q
    if q >= 0.5:
        return 1.0
    return (q / p) ** z


# ── Render ────────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M6 · Security Score")
    st.caption(
        "Coste estimado de un ataque del 51% sobre Bitcoin y probabilidad de éxito "
        "según la profundidad de confirmación — basado en Nakamoto (2008), §11."
    )

    with st.spinner("Obteniendo hash rate de la red..."):
        try:
            net = fetch_network_hashrate()
        except Exception as e:
            st.error(f"Error al obtener datos: {e}")
            return

    # ── Parámetros ajustables ─────────────────────────────────────────────────
    st.subheader("Parámetros del modelo")
    col1, col2, col3 = st.columns(3)
    miner_price  = col1.number_input("Precio por miner (USD)", value=MINER_PRICE_USD, step=100)
    elec_price   = col2.number_input("Electricidad (USD/kWh)", value=ELECTRICITY_KWH_USD, step=0.01, format="%.3f")
    attacker_pct = col3.slider("Fracción del hash rate del atacante (%)", 10, 60, 51)

    attacker_q   = attacker_pct / 100
    cost         = compute_attack_cost(net["hashrate_ths"] * attacker_q / 0.51,
                                       elec_price, miner_price)
    # Recalculamos para la fracción exacta del slider
    target_ths   = net["hashrate_ths"] * attacker_q
    units        = int(np.ceil(target_ths / MINER_HASHRATE_THS))
    hw_cost      = units * miner_price
    power_kw     = units * MINER_POWER_W / 1000
    elec_hour    = power_kw * elec_price
    amort_hour   = hw_cost / (18 * 30 * 24)
    total_hour   = elec_hour + amort_hour

    st.divider()

    # ── Métricas principales ──────────────────────────────────────────────────
    st.subheader("Coste estimado del ataque")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hash rate de la red", f"{net['hashrate_ehs']:.1f} EH/s")
    col2.metric("Miners necesarios", f"{units:,}")
    col3.metric("Coste de hardware", f"${hw_cost/1e9:.2f} B")
    col4.metric("Coste operativo/hora", f"${total_hour:,.0f}/h")

    col1b, col2b, col3b = st.columns(3)
    col1b.metric("Potencia total requerida", f"{power_kw/1e6:.2f} TW")
    col2b.metric("Solo electricidad/hora",   f"${elec_hour:,.0f}/h")
    col3b.metric("Amortización hardware/hora", f"${amort_hour:,.0f}/h")

    st.info(
        f"Para controlar el **{attacker_pct}%** del hash rate actual de Bitcoin "
        f"({net['hashrate_ehs']:.1f} EH/s), un atacante necesitaría **{units:,} mineros** "
        f"(Antminer S21 Pro) con un coste de hardware de **${hw_cost/1e9:.2f} B** "
        f"y un coste operativo de **${total_hour:,.0f} USD/hora**."
    )

    st.divider()

    # ── Gráfico 1: Desglose del coste ─────────────────────────────────────────
    st.subheader("Desglose del coste por hora")

    fig_cost = go.Figure(go.Bar(
        x=["Electricidad/hora", "Amortización HW/hora", "Total/hora"],
        y=[elec_hour, amort_hour, total_hour],
        marker_color=["#1565c0", "#e65100", "#b71c1c"],
        text=[f"${v:,.0f}" for v in [elec_hour, amort_hour, total_hour]],
        textposition="outside",
    ))
    fig_cost.update_layout(
        yaxis_title="USD / hora",
        height=320,
        showlegend=False,
    )
    st.plotly_chart(fig_cost, use_container_width=True)

    st.divider()

    # ── Gráfico 2: Probabilidad de éxito vs confirmaciones (Nakamoto §11) ─────
    st.subheader("Probabilidad de éxito del ataque vs profundidad de confirmación")
    st.markdown(
        "Según Nakamoto (2008) §11, la probabilidad de que un atacante con fracción **q** "
        "del hash rate revierta una transacción decae exponencialmente con el número de "
        "confirmaciones **z**. Fórmula: P ≈ (q/p)^z para q < 0.5."
    )

    z_values = np.arange(0, 21)
    q_values = [0.10, 0.20, 0.30, 0.40, 0.49, attacker_q]
    colors   = ["#43a047", "#1565c0", "#ff6d00", "#e53935", "#6a1b9a", "#000000"]
    labels   = ["q=10%", "q=20%", "q=30%", "q=40%", "q=49%", f"q={attacker_pct}% (slider)"]

    fig_nak = go.Figure()
    for q, color, label in zip(q_values, colors, labels):
        probs = [nakamoto_attack_probability(q, int(z)) for z in z_values]
        fig_nak.add_trace(go.Scatter(
            x=z_values, y=probs,
            mode="lines+markers",
            name=label,
            line=dict(color=color, width=2 if label.endswith("(slider)") else 1.5,
                      dash="solid" if label.endswith("(slider)") else "dot"),
            marker=dict(size=5),
        ))

    fig_nak.add_hline(y=0.001, line_dash="dash", line_color="#888",
                      annotation_text="0.1% probabilidad", annotation_position="right")
    fig_nak.update_layout(
        xaxis_title="Número de confirmaciones (z)",
        yaxis_title="Probabilidad de éxito del ataque",
        yaxis_type="log",
        height=380,
        legend=dict(x=0.65, y=0.99),
    )
    st.plotly_chart(fig_nak, use_container_width=True)

    st.markdown(
        "**Conclusión práctica:** con 6 confirmaciones (~1 hora), incluso un atacante con "
        "el 40% del hash rate tiene una probabilidad de éxito < 0.1%. "
        "Por eso Bitcoin considera 6 confirmaciones como 'definitivo' para transacciones grandes."
    )

    st.divider()

    # ── Gráfico 3: Coste vs fracción del hash rate ────────────────────────────
    st.subheader("Coste operativo/hora según fracción del hash rate controlada")

    fractions = np.linspace(0.01, 0.60, 60)
    costs_hour = []
    for f in fractions:
        t_ths  = net["hashrate_ths"] * f
        u      = int(np.ceil(t_ths / MINER_HASHRATE_THS))
        hw     = u * miner_price
        el_h   = (u * MINER_POWER_W / 1000) * elec_price
        am_h   = hw / (18 * 30 * 24)
        costs_hour.append(el_h + am_h)

    fig_frac = go.Figure()
    fig_frac.add_trace(go.Scatter(
        x=fractions * 100, y=costs_hour,
        mode="lines", name="Coste/hora",
        line=dict(color="#1565c0", width=2),
        fill="tozeroy", fillcolor="rgba(21,101,192,0.1)",
    ))
    fig_frac.add_vline(
        x=51, line_dash="dash", line_color="#e53935",
        annotation_text="51%", annotation_position="top right",
    )
    fig_frac.update_layout(
        xaxis_title="Fracción del hash rate controlada (%)",
        yaxis_title="Coste total (USD/hora)",
        height=300,
    )
    st.plotly_chart(fig_frac, use_container_width=True)

    # ── Tabla resumen ─────────────────────────────────────────────────────────
    with st.expander("Ver tabla completa de costes por fracción"):
        rows = []
        for f in [0.10, 0.20, 0.30, 0.40, 0.51, 0.60]:
            t   = net["hashrate_ths"] * f
            u   = int(np.ceil(t / MINER_HASHRATE_THS))
            hw  = u * miner_price
            el  = (u * MINER_POWER_W / 1000) * elec_price
            am  = hw / (18 * 30 * 24)
            rows.append({
                "Fracción (%)":     f"{f*100:.0f}%",
                "Miners":           f"{u:,}",
                "Hardware (USD)":   f"${hw/1e9:.3f} B",
                "Electricidad/h":   f"${el:,.0f}",
                "Total/h":          f"${el+am:,.0f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.caption(
        "Referencia: Nakamoto, S. (2008). Bitcoin: A Peer-to-Peer Electronic Cash System. §11. "
        "Hardware: Antminer S21 Pro (234 TH/s, 3,510 W, ~$2,400). "
        "Electricidad: $0.05/kWh (media industrial global)."
    )