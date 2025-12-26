import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

# =====================
# Variables de entorno
# =====================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SITE_ID = "MLA"
st.write("SITE_ID:", SITE_ID)

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Faltan variables de entorno: CLIENT_ID / CLIENT_SECRET / REDIRECT_URI")
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
# OAuth helpers
# =====================
def get_auth_url():
    return (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state=railway"
    )

def exchange_code_for_token(code: str):
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=10)
    if r.status_code != 200:
        st.error("❌ Error OAuth")
        st.code(r.text)
        return None
    return r.json().get("access_token")

# =====================
# Mercado Libre API
# =====================
@st.cache_data(ttl=86400)
def get_categories():
    url = f"https://api.mercadolibre.com/sites/{SITE_ID}/categories"
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return []
    return r.json()

@st.cache_data(ttl=3600)
def get_best_sellers(token, category_id):
    url = f"https://api.mercadolibre.com/highlights/{SITE_ID}/category/{category_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get("content", [])

def get_item(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()

def get_item_visits(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}/visits/time_window"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"last": 30, "unit": "day"}
    r = requests.get(url, headers=headers, params=params, timeout=10)
    return r.json().get("total_visits", "N/A")

def get_item_rating(token, item_id):
    url = f"https://api.mercadolibre.com/reviews/item/{item_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return "N/A", {}
    data = r.json()
    return data.get("rating_average", "N/A"), data.get("rating_levels", {})

def get_seller_reputation(token, seller_id):
    url = f"https://api.mercadolibre.com/users/{seller_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return {}
    rep = r.json().get("seller_reputation", {})
    tx = rep.get("transactions", {})
    return {
        "nivel": rep.get("level_id", "N/A"),
        "power": rep.get("power_seller_status", "N/A"),
        "total": tx.get("total", "N/A"),
    }

def format_rating_levels(levels):
    return (
        f"⭐ {levels.get('one_star',0)} | "
        f"⭐⭐ {levels.get('two_star',0)} | "
        f"⭐⭐⭐ {levels.get('three_star',0)} | "
        f"⭐⭐⭐⭐ {levels.get('four_star',0)} | "
        f"⭐⭐⭐⭐⭐ {levels.get('five_star',0)}"
    )

def fetch_product_data(token, item, position):
    rating, levels = get_item_rating(token, item["id"])
    seller = get_seller_reputation(token, item["seller_id"])
    return {
        "Posición": position,
        "Título": item.get("title"),
        "Precio": item.get("price"),
        "Ventas": item.get("sold_quantity"),
        "Visitas 30d": get_item_visits(token, item["id"]),
        "Rating": rating,
        "Distribución Rating": format_rating_levels(levels),
        "Nivel Vendedor": seller.get("nivel"),
        "Power Seller": seller.get("power"),
        "Link": item.get("permalink"),
    }

# =====================
# UI
# =====================
st.set_page_config("MercadoLibre Explorer", "🛒", layout="wide")
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
# Sidebar – categorías
# =====================
categories = get_categories()

cat_map = {
    c["name"]: c["id"]
    for c in categories
    if isinstance(c, dict) and "id" in c and "name" in c
}

if not cat_map:
    st.error("❌ No se pudieron cargar las categorías")
    st.stop()

st.sidebar.header("Filtros")
category_name = st.sidebar.selectbox("Categoría", sorted(cat_map.keys()))
limit = st.sidebar.slider("Cantidad de items", 5, 20, 10)

# =====================
# Buscar
# =====================
if st.sidebar.button("🔍 Buscar"):
    with st.spinner("Consultando ranking de más vendidos..."):
        highlights = get_best_sellers(token, cat_map[category_name])
        records = []

        for h in highlights[:limit]:
            if h.get("type") == "ITEM":
                item = get_item(token, h["id"])
                if item:
                    records.append(fetch_product_data(token, item, h["position"]))

        if not records:
            st.warning("Esta categoría no tiene ranking de más vendidos.")
        st.session_state["data"] = records

# =====================
# Resultados
# =====================
if st.session_state["data"]:
    df = pd.DataFrame(st.session_state["data"])
    st.subheader(f"Top {len(df)} – {category_name}")
    st.dataframe(df, use_container_width=True)

    st.plotly_chart(
        px.bar(df, x="Título", y="Precio", title="Precio por producto"),
        use_container_width=True,
    )

    st.plotly_chart(
        px.scatter(df, x="Precio", y="Ventas", hover_data=["Título"], title="Precio vs Ventas"),
        use_container_width=True,
    )

    csv = df.to_csv(index=False)
    st.download_button(
        "📥 Descargar CSV",
        csv,
        file_name="ranking_ml.csv",
        mime="text/csv",
    )
