"""
Blockchain API client.

Provides helper functions to fetch blockchain data from public APIs.
"""

import requests

BASE_URL = "https://blockchain.info"


def get_latest_block() -> dict:
    """Return the latest block summary."""
    response = requests.get(f"{BASE_URL}/latestblock", timeout=10)
    response.raise_for_status()
    return response.json()


def get_block(block_hash: str) -> dict:
    """Return full details for a block identified by *block_hash*."""
    response = requests.get(
        f"{BASE_URL}/rawblock/{block_hash}", timeout=10
    )
    response.raise_for_status()
    return response.json()


def get_difficulty_history(n_points: int = 100) -> list[dict]:
    """Return the last *n_points* difficulty values as a list of dicts."""
    response = requests.get(
        f"{BASE_URL}/charts/difficulty",
        params={"timespan": "1year", "format": "json", "sampled": "true"},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("values", [])[-n_points:]

# ---------------------------------------------------------------------------
# Milestone 2 — observaciones criptográficas (Session 1)
# ---------------------------------------------------------------------------
# Para probar la conexión ejecuta este archivo directamente:
#   python api/blockchain_client.py
#
# El hash del bloque empieza con muchos ceros → es el resultado del doble
# SHA-256 que debe ser menor que el target. Esos ceros son la prueba del trabajo.
#
# El campo 'bits' codifica el target en formato compacto (256 bits).
# Los mineros ajustan el nonce hasta encontrar un hash < target.
#
# El nonce es el número que los mineros incrementan en cada intento.
# Con 32 bits (~4 mil millones de valores) a veces no es suficiente y
# deben cambiar otros campos del header (extra nonce en la coinbase tx).

if __name__ == "__main__":
    block = get_latest_block()
    print("Height:      ", block.get("height"))
    print("Hash:        ", block.get("hash"))
    print("Nonce:       ", block.get("nonce"))
    print("Transactions:", block.get("n_tx"))

# LEADING ZEROS: el hash empieza con muchos ceros porque debe ser menor
    # que el target. Cada cero hex representa 4 bits de trabajo demostrado.
    # Cuantos más ceros, más intentos necesitó el minero → mayor dificultad.
    hash_val = block.get("hash", "")
    leading_zeros = len(hash_val) - len(hash_val.lstrip("0"))
    print(f"Leading zero hex digits: {leading_zeros} ({leading_zeros * 4} bits)")

    # BITS / TARGET: el campo 'bits' codifica el target en formato compacto.
    # bits = 0xAABBCCDD → target = 0xBBCCDD * 256^(AA-3)
    # El hash del bloque es válido solo si hash < target (Proof of Work).
    # A mayor dificultad, menor target → más ceros exigidos en el hash.