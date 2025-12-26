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
    )

def exchange_code_for_token(code: str):
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    r = requests.post(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )

    if r.status_code != 200:
        st.error("❌ Error al obtener access_token")
        st.code(r.text)
        return None

    return r.json().get("access_token")

def get_me(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(ME_URL, headers=headers, timeout=10)
    r.raise_for_status()
    return r.json()

# =========================
# App principal
# =========================
st.set_page_config(page_title="Mercado Libre OAuth", layout="centered")
st.title("🔐 Login Mercado Libre")

# ---- Debug temporal (podés borrar después) ----
st.write("CLIENT_ID:", CLIENT_ID)
st.write("REDIRECT_URI:", REDIRECT_URI)

# =========================
# Flujo OAuth
# =========================
params = st.query_params

# 1️⃣ Si vuelve de ML con ?code=
if "code" in params and not st.session_state["access_token"]:
    code = params["code"]
    token = exchange_code_for_token(code)

    if token:
        st.session_state["access_token"] = token
        st.query_params.clear()
        st.success("✅ Login exitoso")
        st.rerun()
    else:
        st.stop()

# 2️⃣ Si NO está logueado → mostrar botón login
if not st.session_state["access_token"]:
    st.info("Iniciá sesión con Mercado Libre para continuar")
    st.markdown(
        f"[👉 Iniciar sesión en Mercado Libre]({get_auth_url()})",
        unsafe_allow_html=True,
    )
    st.stop()

# 3️⃣ Usuario logueado
st.success("🔓 Autenticado correctamente")

try:
    me = get_me(st.session_state["access_token"])
    st.subheader("👤 Usuario Mercado Libre")
    st.json(me)
except Exception as e:
    st.error(f"Error al consultar /users/me: {e}")
