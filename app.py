import os
import requests
import streamlit as st

# =========================
# Configuración OAuth ML
# =========================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
ME_URL = "https://api.mercadolibre.com/users/me"

# =========================
# Validaciones iniciales
# =========================
if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Faltan variables de entorno (CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)")
    st.stop()

# =========================
# Session State
# =========================
if "access_token" not in st.session_state:
    st.session_state["access_token"] = None

# =========================
# Funciones OAuth
# =========================
def get_auth_url():
    return (
        f"{AUTH_URL}"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state=railway_{os.urandom(8).hex()}"
    )

def exchange_code_for_token(code: str) -> str | None:
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    r = requests.post(TOKEN_URL, data=payload, timeout=10_
