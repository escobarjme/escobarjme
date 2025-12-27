import streamlit as st
import requests
import os

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

# Header OBLIGATORIO para Railway
HEADERS_PUBLIC = {
    "User-Agent": "Mozilla/5.0"
}

# =========================
# OAUTH
# =========================
def exchange_code_for_token(code):
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=10)
    if r.status_code != 200:
        st.error("❌ Error obteniendo token")
        st.json(r.json())
        return None
    return r.json()

# =========================
# API PUBLICA (SIN TOKEN)
# =========================
def get_categories():
    r = requests.get(
        f"{API_BASE}/sites/{SITE_ID}/categories",
        headers=HEADERS_PUBLIC,
        timeout=10
    )
    if r.status_code != 200:
        return []
    return r.json()

def get_category_detail(category_id):
    r = requests.get(
        f"{API_BASE}/categories/{category_id}",
        headers=HEADERS_PUBLIC,
        timeout=10
    )
    if r.status_code != 200:
        return None
    return r.json()

# =========================
# API PRIVADA (CON TOKEN)
# =========================
def search_products(category_id, access_token, limit=20):
    headers = {
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "Mozilla/5.0"
    }
    params = {
        "category": category_id,
        "limit": limit
    }
    r = requests.get(
        f"{API_BASE}/sites/{SITE_ID}/search",
        headers=headers,
        params=params,
        timeout=10
    )
    if r.status_code != 200:
        return []
    return r.json().get("results", [])

# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title="MercadoLibre Analyzer", layout="wide")
st.title("📦 MercadoLibre – Analizador de Categorías")

# -------------------------
# OAuth callback
# -------------------------
query_params = st.query_params
if "code" in query_params and "token" not in st.session_state:
    token_data = exchange_code_for_token(query_params["code"])
    if token_data:
        st.session_state["token"] = token_data["access_token"]
        st.success("✅ Login exitoso")

# -------------------------
# Login
# -------------------------
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
# APP PRINCIPAL
# =========================
st.success("🔓 Autenticado correctamente")

# Cargar categorías
categories = get_categories()
if not categories:
    st.error("❌ No se pudieron cargar las categorías")
    st.stop()

category_names = {c["name"]: c["id"] for c in categories}

selected_name = st.selectbox(
    "Seleccioná una categoría",
    sorted(category_names.keys())
)

category_id = category_names[selected_name]

# Detalle categoría
category_detail = get_category_detail(category_id)
if category_detail:
    st.subheader("📂 Detalle de categoría")
    st.json({
        "id": category_detail["id"],
        "name": category_detail["name"],
        "path": [p["name"] for p in category_detail.get("path_from_root", [])]
    })

# Buscar productos
if st.button("🔍 Buscar productos"):
    products = search_products(category_id, st.session_state["token"], limit=20)

    if not products:
        st.warning("No se encontraron productos")
    else:
        st.subheader("🛒 Productos")
        for p in products:
            with st.container():
                st.markdown(f"### {p['title']}")
                st.write(f"💰 Precio: ${p['price']}")
                st.write(f"🏬 Vendedor: {p['seller']['id']}")
                st.markdown(f"[Ver producto]({p['permalink']})")
                st.divider()
