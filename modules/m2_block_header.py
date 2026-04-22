
"""
modules/m2_block_header.py
M2 · Block Header Analyzer

Herramienta de inspección del header de 80 bytes de un bloque Bitcoin.
Verifica el Proof of Work localmente con hashlib (SHA-256 doble).
Enfoque: análisis criptográfico técnico.
"""

import hashlib
import struct
import requests
import pandas as pd
import streamlit as st

BASE_URL = "https://blockstream.info/api"


# ── Funciones criptográficas ──────────────────────────────────────────────────

def fetch_block_hash_at_tip() -> str:
    r = requests.get(f"{BASE_URL}/blocks/tip/hash", timeout=10)
    r.raise_for_status()
    return r.text.strip()


def fetch_block_header_hex(block_hash: str) -> str:
    """Devuelve el header del bloque en hexadecimal (80 bytes = 160 chars hex)."""
    r = requests.get(f"{BASE_URL}/block/{block_hash}/header", timeout=10)
    r.raise_for_status()
    return r.text.strip()


def parse_header(header_hex: str) -> dict:
    """
    Parsea los 80 bytes del header de Bitcoin campo a campo.

    Estructura (little-endian en wire format):
      bytes  0– 3 : version      (int32 LE)
      bytes  4–35 : prev_hash    (32 bytes, LE → mostrar BE invertido)
      bytes 36–67 : merkle_root  (32 bytes, LE → mostrar BE invertido)
      bytes 68–71 : timestamp    (uint32 LE, Unix time)
      bytes 72–75 : bits         (uint32 LE, target compacto NBits)
      bytes 76–79 : nonce        (uint32 LE)
    """
    raw = bytes.fromhex(header_hex)
    assert len(raw) == 80, f"Se esperan 80 bytes, se recibieron {len(raw)}"

    version     = struct.unpack_from("<i", raw, 0)[0]
    prev_hash   = raw[4:36][::-1].hex()    # invertir LE→BE para mostrar
    merkle_root = raw[36:68][::-1].hex()
    timestamp   = struct.unpack_from("<I", raw, 68)[0]
    bits        = struct.unpack_from("<I", raw, 72)[0]
    nonce       = struct.unpack_from("<I", raw, 76)[0]

    return {
        "version":     version,
        "prev_hash":   prev_hash,
        "merkle_root": merkle_root,
        "timestamp":   timestamp,
        "bits":        bits,
        "nonce":       nonce,
        "raw_bytes":   raw,
        "raw_hex":     header_hex,
    }


def bits_to_target(bits: int) -> int:
    """
    Decodifica el campo 'bits' (formato compacto NBits) al target entero de 256 bits.
    bits = 0xAABBCCDD → target = 0xBBCCDD * 256^(AA-3)
    """
    exponent    = (bits >> 24) & 0xFF
    coefficient = bits & 0x007FFFFF
    return coefficient << (8 * (exponent - 3))


def double_sha256(data: bytes) -> bytes:
    """SHA-256(SHA-256(data)) — función de hash usada en Bitcoin."""
    return hashlib.sha256(hashlib.sha256(data).digest()).digest()


def verify_pow(header: dict) -> dict:
    """
    Verifica el Proof of Work localmente:
    1. Toma los 80 bytes raw del header
    2. Calcula SHA256(SHA256(header)) → resultado en little-endian
    3. Invierte a big-endian para comparar y mostrar
    4. Comprueba que hash_int < target
    """
    hash_le  = double_sha256(header["raw_bytes"])
    hash_be  = hash_le[::-1]
    hash_hex = hash_be.hex()
    hash_int = int(hash_hex, 16)

    target     = bits_to_target(header["bits"])
    target_hex = f"{target:064x}"
    valid      = hash_int < target

    lz_bits = 256 - hash_int.bit_length() if hash_int > 0 else 256
    lz_hex  = len(hash_hex) - len(hash_hex.lstrip("0"))

    return {
        "hash_hex":   hash_hex,
        "target_hex": target_hex,
        "valid":      valid,
        "lz_bits":    lz_bits,
        "lz_hex":     lz_hex,
        "hash_int":   hash_int,
        "target_int": target,
    }


# ── Render ────────────────────────────────────────────────────────────────────

def render() -> None:
    st.header("M2 · Block Header Analyzer")
    st.caption("Inspección del header de 80 bytes y verificación local del Proof of Work con hashlib")

    use_latest = st.checkbox("Usar el último bloque de la red", value=True)
    custom_hash = st.text_input(
        "O introduce un block hash:",
        placeholder="000000000000000000028f3a...",
        disabled=use_latest,
        key="m2_hash",
    )

    if not st.button("Analizar header", key="m2_analyze"):
        st.info("Selecciona un bloque y pulsa Analizar header.")
        return

    with st.spinner("Obteniendo y analizando header..."):
        try:
            block_hash = fetch_block_hash_at_tip() if use_latest else custom_hash.strip()
            if not block_hash:
                st.error("Introduce un block hash válido.")
                return
            header_hex = fetch_block_header_hex(block_hash)
            header     = parse_header(header_hex)
            pow        = verify_pow(header)
        except Exception as e:
            st.error(f"Error: {e}")
            return

    # ── Resultado de verificación ─────────────────────────────────────────────
    if pow["valid"]:
        st.success("✅ Proof of Work VÁLIDO — hash calculado localmente con hashlib es menor que el target.")
    else:
        st.error("❌ Proof of Work INVÁLIDO.")

    st.divider()

    # ── Campos del header — una fila visual por campo ────────────────────────
    st.subheader("Campos del header (80 bytes)")

    from datetime import datetime, timezone
    ts_human = datetime.fromtimestamp(header["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    field_defs = [
        ("#1565c0", "version",         "bytes 0–3",   f"{header['version']} (0x{header['version']:08x})",  "Versión del protocolo Bitcoin"),
        ("#2e7d32", "prev_block_hash", "bytes 4–35",  header["prev_hash"],                                  "Hash del bloque anterior — forma la cadena"),
        ("#6a1b9a", "merkle_root",     "bytes 36–67", header["merkle_root"],                                "Raíz del árbol Merkle de transacciones"),
        ("#e65100", "timestamp",       "bytes 68–71", f"{header['timestamp']} → {ts_human}",                "Tiempo Unix declarado por el minero"),
        ("#b71c1c", "bits",            "bytes 72–75", f"0x{header['bits']:08x}",                            "Target compacto — codifica la dificultad"),
        ("#00695c", "nonce",           "bytes 76–79", f"{header['nonce']:,} (0x{header['nonce']:08x})",     "Número ajustado por el minero para cumplir el PoW"),
    ]

    for color, name, byte_range, value, desc in field_defs:
        col_a, col_b = st.columns([1, 3])
        with col_a:
            st.markdown(
                f'<div style="background:{color}22;border-left:4px solid {color};'
                f'padding:8px 12px;border-radius:4px;margin-bottom:4px">'
                f'<span style="color:{color};font-weight:bold;font-size:0.85em">{name}</span><br>'
                f'<span style="color:#888;font-size:0.75em">{byte_range}</span></div>',
                unsafe_allow_html=True,
            )
        with col_b:
            st.markdown(
                f'<div style="padding:6px 0">'
                f'<code style="font-size:0.78em;word-break:break-all">{value}</code><br>'
                f'<span style="color:#888;font-size:0.8em">{desc}</span></div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # ── Nonce: análisis visual ────────────────────────────────────────────────
    st.subheader("Análisis del Nonce")
    st.caption("El nonce es un entero de 32 bits (0 a 4.294.967.295). El minero lo incrementa hasta que el hash cumple el target.")

    nonce_val = header["nonce"]
    nonce_max = 0xFFFFFFFF
    nonce_pct = nonce_val / nonce_max * 100

    col1, col2, col3 = st.columns(3)
    col1.metric("Nonce (decimal)", f"{nonce_val:,}")
    col2.metric("Nonce (hex)", f"0x{nonce_val:08x}")
    col3.metric("% del espacio recorrido", f"{nonce_pct:.1f}%")

    st.markdown(
        f'<div style="margin:8px 0 4px 0;font-size:0.82em;color:#555">Posición del nonce en el espacio de 2³² valores:</div>'
        f'<div style="background:#e0e0e0;border-radius:6px;height:18px;width:100%">'
        f'<div style="background:#00695c;height:18px;border-radius:6px;width:{nonce_pct:.2f}%"></div>'
        f'</div>'
        f'<div style="font-size:0.75em;color:#888;margin-top:4px">0 &nbsp;→&nbsp; 4.294.967.295 (2³²−1)</div>',
        unsafe_allow_html=True,
    )

    if nonce_pct > 90:
        st.warning(
            "⚠️ El minero recorrió casi todo el espacio de nonce. "
            "Probablemente tuvo que modificar el extra nonce de la coinbase transaction para encontrar el bloque."
        )
    else:
        st.info(
            f"El minero encontró el bloque en el {nonce_pct:.1f}% del espacio disponible "
            f"(≈ {nonce_val:,} intentos con este header concreto)."
        )

    st.divider()

    # ── Verificación del Merkle Root ──────────────────────────────────────────
    st.subheader("Verificación del Merkle Root")
    st.caption("Comprobamos que el merkle_root parseado del header coincide con el que devuelve la API.")

    try:
        bh = fetch_block_hash_at_tip() if use_latest else custom_hash.strip()
        r_meta = requests.get(f"{BASE_URL}/block/{bh}", timeout=10)
        r_meta.raise_for_status()
        api_merkle = r_meta.json().get("merkle_root", "")

        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.markdown("**Merkle root (parseado del header localmente):**")
            st.code(header["merkle_root"], language="text")
        with col_m2:
            st.markdown("**Merkle root (devuelto por la API):**")
            st.code(api_merkle, language="text")

        if header["merkle_root"].lower() == api_merkle.lower():
            st.success("✅ Merkle root coincide — el resumen de transacciones es consistente.")
        else:
            st.error("❌ Merkle root no coincide.")

        st.markdown(
            "**¿Qué garantiza el Merkle root?** Es el hash raíz de un árbol binario donde cada hoja "
            "es el txid de una transacción. Si cualquier transacción cambia, la raíz cambia → "
            "el hash del bloque ya no cumple el PoW → la manipulación es detectable sin "
            "descargar todas las transacciones del bloque."
        )
    except Exception as e:
        st.warning(f"No se pudo verificar el Merkle root: {e}")

    st.divider()

    # ── Header raw coloreado por campos ──────────────────────────────────────
    st.subheader("Header raw (160 hex chars = 80 bytes)")
    st.caption("Cada color corresponde a un campo. Orden wire format (little-endian).")

    colors = ["#1565c0", "#2e7d32", "#6a1b9a", "#e65100", "#b71c1c", "#00695c"]
    labels = ["version", "prev_hash", "merkle_root", "timestamp", "bits", "nonce"]
    slices = [
        header_hex[0:8],
        header_hex[8:72],
        header_hex[72:136],
        header_hex[136:144],
        header_hex[144:152],
        header_hex[152:160],
    ]

    colored = "".join(
        f'<span style="color:{c};font-weight:bold" title="{l}">{s}</span>'
        for c, l, s in zip(colors, labels, slices)
    )
    st.markdown(
        f'<code style="font-size:0.72em;word-break:break-all;line-height:1.8">{colored}</code>',
        unsafe_allow_html=True,
    )
    legend = " &nbsp;&nbsp; ".join(
        f'<span style="color:{c}">■</span> {l}' for c, l in zip(colors, labels)
    )
    st.markdown(f"<small>{legend}</small>", unsafe_allow_html=True)

    st.divider()

    # ── Verificación paso a paso ──────────────────────────────────────────────
    st.subheader("Verificación del Proof of Work — paso a paso")

    st.markdown("**Paso 1 — Calcular SHA256(SHA256(header_bytes)):**")
    st.code(
        f"import hashlib\n"
        f"raw      = bytes.fromhex(header_hex)               # 80 bytes\n"
        f"hash_le  = hashlib.sha256(hashlib.sha256(raw).digest()).digest()\n"
        f"hash_hex = hash_le[::-1].hex()                     # invertir LE→BE\n"
        f"# resultado: {pow['hash_hex']}",
        language="python",
    )

    st.markdown("**Paso 2 — Decodificar `bits` → target de 256 bits:**")
    exp  = (header["bits"] >> 24) & 0xFF
    coef = header["bits"] & 0x007FFFFF
    st.code(
        f"bits        = 0x{header['bits']:08x}\n"
        f"exponent    = 0x{exp:02x}  ({exp})\n"
        f"coefficient = 0x{coef:06x}\n"
        f"target      = coefficient << (8 * (exponent - 3))\n"
        f"# resultado: {pow['target_hex']}",
        language="python",
    )

    st.markdown("**Paso 3 — Comparar hash < target:**")
    sym = "<" if pow["valid"] else "≥"
    st.code(
        f"hash   = 0x{pow['hash_hex']}\n"
        f"target = 0x{pow['target_hex']}\n"
        f"hash {sym} target  →  {'VÁLIDO ✅' if pow['valid'] else 'INVÁLIDO ❌'}",
        language="text",
    )

    st.divider()

    # ── Ceros iniciales ───────────────────────────────────────────────────────
    st.subheader("Ceros iniciales del hash")

    h  = pow["hash_hex"]
    lz = pow["lz_hex"]
    st.markdown(
        f'<code style="font-size:0.8em">'
        f'<span style="color:#00c853;font-weight:bold">{h[:lz]}</span>'
        f'<span>{h[lz:]}</span></code>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    col1.metric("Ceros hex iniciales", pow["lz_hex"])
    col2.metric("Ceros en bits", pow["lz_bits"])
    col3.metric("Probabilidad aprox.", f"1 / 2^{pow['lz_bits']}")