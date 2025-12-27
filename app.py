import os
import requests
import streamlit as st
import pandas as pd

# =====================
# CONFIG
# =====================
st.set_page_config(
    page_title="MercadoLibre Argentina – Más Vendidos",
    layout="wide"
)

API_BASE = "https://api.mercadolibre.com"
SITE_ID = "MLA"

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Faltan variables de entorno en Railway")
    st.stop()

AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
TOKEN_URL = f"{API_BASE}/oauth/token"

CATEGORIES = {
    "Televisores": "MLA1002",
    "Celulares": "MLA1055",
    "Notebooks": "MLA1652",
    "Zapatillas": "MLA109027",
}

# =====================
# SESSION STATE
# =====================
st.session_state.setdefault("access_token", None)
st.session_state.setdefault("data", [])

# =====================
# OAUTH
# =====================
def get_auth_url():
    return (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )

def exchange_code_for_token(code):
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=15)
    if r.status_code != 200:
        st.error("❌ Error OAuth")
        st.text(r.text)
        return None
    return r.json().get("access_token")

# =====================
# API CALLS
# =====================
@st.cache_data(ttl=300)
def get_highlights(token, category_id):
    url = f"{API_BASE}/highlights/{SITE_ID}/category/{category_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=15)
    return r.json().get("content", []) if r.status_code == 200 else []

@st.cache_data(ttl=300)
def get_product(token, product_id):
    r = requests.get(
        f"{API_BASE}/products/{product_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15
    )
    return r.json() if r.status_code == 200 else None

@st.cache_data(ttl=300)
def get_item(token, item_id):
    r = requests.get(
        f"{API_BASE}/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15
    )
    return r.json() if r.status_code == 200 else None

# =====================
# FORMAT
# =====================
def format_item(item, position):
    return {
        "Posición": position,
        "ID": item.get("id"),
        "Título": item.get("title"),
        "Precio": item.get("price"),
        "Ventas": item.get("sold_quantity"),
        "Link": item.get("permalink"),
    }

# =====================
# UI
# =====================
st.title("🛒 MercadoLibre Argentina – Más Vendidos")

# OAuth callback
params = st.query_params
if "code" in params and not st.session_state["access_token"]:
    token = exchange_code_for_token(params["code"])
    if token:
        st.session_state["access_token"] = token
        st.query_params.clear()
        st.rerun()

if not st.session_state["access_token"]:
    st.link_button("🔐 Login con MercadoLibre", get_auth_url())
    st.stop()

token = st.session_state["access_token"]

# Sidebar
with st.sidebar:
    st.header("Filtros")
    category_name = st.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.slider("Cantidad de productos", 5, 50, 20)

if st.sidebar.button("🔍 Buscar"):
    with st.spinner("Consultando ranking..."):
        records = []
        highlights = get_highlights(token, CATEGORIES[category_name])

        for h in highlights[:limit]:
            h_type = h.get("type")
            product_id = h.get("id")
            position = h.get("position", 0)

            st.write(f"Procesando {h_type}: {product_id}")

            item_id = None

            if h_type == "PRODUCT":
                product = get_product(token, product_id)
                if product and product.get("buy_box_winner"):
                    item_id = product["buy_box_winner"].get("item_id")

            elif h_type == "ITEM":
                item_id = product_id

            if not item_id:
                continue

            item = get_item(token, item_id)
            if item and item.get("title"):
                records.append(format_item(item, position))

        if not records:
            st.warning("No se encontraron datos para esta categoría.")
        else:
            df = pd.DataFrame(records).sort_values("Posición")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                "⬇️ Descargar CSV",
                df.to_csv(index=False),
                "ranking_ml.csv",
                "text/csv"
            )
