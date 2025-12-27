import streamlit as st
import requests

# =========================
# CONFIG
# =========================
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]

SITE_ID = "MLA"
API_BASE = "https://api.mercadolibre.com"
AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

HEADERS_PUBLIC = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Accept-Language": "es-AR,es;q=0.9"
}

# =========================
# OAUTH
# =========================
def exchange_code_for_token(code):
    r = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI
        },
        timeout=10
    )
    if r.status_code != 200:
        st.error("❌ Error token")
        st.code(r.text)
        return None
    return r.json()

# =========================
# API PUBLICA
# =========================
def get_categories():
    r = requests.get(
        f"{API_BASE}/sites/{SITE_ID}/categories",
        headers=HEADERS_PUBLIC,
        timeout=10
    )

    # 🔥 DEBUG REAL
    if r.status_code != 200:
        st.error("❌ Error al obtener categorías")
        st.write("Status:", r.status_code)
        st.code(r.text)
        return []

    try:
        return r.json()
    except Exception as e:
        st.error("❌ Respuesta NO es JSON")
        st.code(r.text)
        return []

# =========================
# STREAMLIT
# =========================
st.set_page_config(page_title="ML Analyzer", layout="wide")
st.title("📦 MercadoLibre Argentina – Más Vendidos")

query_params = st.query_params
if "code" in query_params and "token" not in st.session_state:
    token_data = exchange_code_for_token(query_params["code"])
    if token_data:
        st.session_state["token"] = token_data["access_token"]
        st.success("✅ Login exitoso")

if "token" not in st.session_state:
    login_url = (
        f"{AUTH_URL}"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    st.markdown(f"### 🔐 [Iniciar sesión con Mercado Libre]({login_url})")
    st.stop()

# =========================
# APP
# =========================
st.success("🔓 Autenticado")

categories = get_categories()

if not categories:
    st.stop()

category_map = {c["name"]: c["id"] for c in categories}

selected = st.selectbox(
    "Seleccioná una categoría",
    sorted(category_map.keys())
)

st.write("📂 Categoría ID:", category_map[selected])
