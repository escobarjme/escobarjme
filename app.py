import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px

# =====================
# Variables de entorno
# =====================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SITE_ID = os.getenv("SITE_ID", "MLA")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Faltan variables de entorno")
    st.stop()

# =====================
# URLs Mercado Libre
# =====================
AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

# =====================
# Session State
# =====================
st.session_state.setdefault("access_token", None)
st.session_state.setdefault("data", [])

# =====================
# Categorías (HIJAS)
# =====================
CATEGORIES = {
    "Celulares y Smartphones": "MLA1055",
    "Televisores": "MLA1002",
    "Notebooks": "MLA1652",
    "Zapatillas": "MLA109027",
    "Heladeras": "MLA5726",
    "Lavarropas": "MLA5727",
    "Auriculares": "MLA3697",
    "Smartwatches": "MLA126793",
    "Consolas": "MLA373840",
    "Herramientas Eléctricas": "MLA1500",
}

# =====================
# OAuth helpers
# =====================
def get_auth_url():
    return (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state=railway"
    )

def exchange_code_for_token(code):
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=10)
    if r.status_code != 200:
        st.error("❌ Error al obtener token")
        st.text(r.text)
        return None
    return r.json().get("access_token")

# =====================
# API helpers (CACHEADOS)
# =====================
@st.cache_data(ttl=3600)
def get_best_sellers(token, category_id):
    url = f"https://api.mercadolibre.com/highlights/{SITE_ID}/category/{category_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get("content", [])

@st.cache_data(ttl=3600)
def get_product_items(token, product_id):
    url = f"https://api.mercadolibre.com/products/{product_id}/items"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get("results", [])

@st.cache_data(ttl=3600)
def get_item(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()

# =====================
# Normalización de datos
# =====================
def fetch_product_data(item, position):
    return {
        "Posición": position,
        "Título": item.get("title"),
        "Precio": item.get("price"),
        "Ventas": item.get("sold_quantity", 0),
        "Condición": item.get("condition"),
        "Link": item.get("permalink"),
    }

# =====================
# UI
# =====================
st.set_page_config(
    page_title="MercadoLibre – Más Vendidos",
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 MercadoLibre Argentina – Más Vendidos")

# =====================
# OAuth callback
# =====================
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

# =====================
# Sidebar
# =====================
st.sidebar.header("Filtros")
category_name = st.sidebar.selectbox("Categoría", CATEGORIES.keys())
limit = st.sidebar.slider("Cantidad de productos", 5, 20, 10)

if st.sidebar.button("🔍 Buscar"):
    with st.spinner("Consultando ranking..."):
        highlights = get_best_sellers(token, CATEGORIES[category_name])
        records = []

        for h in highlights[:limit]:
            highlight_id = h["id"]
            # 1️⃣ Intentar como ITEM directo (esto funciona en MLA)
            item = get_item(token, highlight_id)
            if item and item.get("title"):
                records.append(
                    fetch_product_data(item, h["position"])
                )
                continue

            # 2️⃣ Fallback: tratarlo como PRODUCT
            product_items = get_product_items(token, highlight_id)
            if product_items:
                item_id = product_items[0].get("item_id")
                if item_id:
                    item = get_item(token, item_id)
                    if item:
                        records.append(
                            fetch_product_data(item, h["position"])
                            )
            st.write("Procesando:", h["id"])


        if not records:
            st.warning("No se encontraron datos para esta categoría.")

        st.session_state["data"] = records

# =====================
# Resultados
# =====================
if st.session_state["data"]:
    df = pd.DataFrame(st.session_state["data"])

    st.subheader("📊 Ranking de más vendidos")
    st.dataframe(df, use_container_width=True)

    st.plotly_chart(
        px.bar(df, x="Título", y="Precio"),
        use_container_width=True,
    )

    st.plotly_chart(
        px.scatter(
            df,
            x="Precio",
            y="Ventas",
            hover_data=["Título"],
        ),
        use_container_width=True,
    )

    csv = df.to_csv(index=False)
    st.download_button(
        "📥 Descargar CSV",
        csv,
        "ranking_ml.csv",
        "text/csv",
    )
