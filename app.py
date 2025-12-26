import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import json

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
        st.error(r.text)
        return None
    return r.json()["access_token"]

# =====================
# Mercado Libre API
# =====================
@st.cache_data(ttl=86400)
def get_categories():
    url = f"https://api.mercadolibre.com/sites/{SITE_ID}/categories"
    return requests.get(url).json()

@st.cache_data(ttl=3600)
def get_best_sellers(token, category_id):
    url = f"https://api.mercadolibre.com/highlights/{SITE_ID}/category/{category_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return []
    return r.json().get("content", [])

def get_item(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return None
    return r.json()

def get_item_visits(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}/visits/time_window"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"last": 30, "unit": "day"}
    r = requests.get(url, headers=headers, params=params)
    return r.json().get("total_visits", "N/A")

def get_item_rating(token, item_id):
    url = f"https://api.mercadolibre.com/reviews/item/{item_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return "N/A", {}
    data = r.json()
    return data.get("rating_average", "N/A"), data.get("rating_levels", {})

def get_seller_reputation(token, seller_id):
    url = f"https://api.mercadolibre.com/users/{seller_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return {}
    rep = r.json().get("seller_reputation", {})
    tx = rep.get("transactions", {})
    return {
        "nivel": rep.get("level_id"),
        "power": rep.get("power_seller_status"),
        "total": tx.get("total"),
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
        "Título": item["title"],
        "Precio": item["price"],
        "Ventas": item.get("sold_quantity"),
        "Visitas 30d": get_item_visits(token, item["id"]),
        "Rating": rating,
        "Distribución Rating": format_rating_levels(levels),
        "Nivel Vendedor": seller.get("nivel"),
        "Power Seller": seller.get("power"),
        "Link": item["permalink"],
    }

# =====================
# UI
# =====================
st.set_page_config("MercadoLibre Explorer", "🛒", layout="wide")
st.title("🛒 MercadoLibre – Más Vendidos")

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

# =====================
# Sidebar
# =====================
categories = get_categories()
cat_map = {c["name"]: c["id"] for c in categories}

st.sidebar.header("Filtros")
category_name = st.sidebar.selectbox("Categoría", cat_map.keys())
limit = st.sidebar.slider("Cantidad", 5, 20, 10)

if st.sidebar.button("🔍 Buscar"):
    with st.spinner("Consultando más vendidos..."):
        highlights = get_best_sellers(token, cat_map[category_name])
        records = []

        for h in highlights[:limit]:
            if h["type"] == "ITEM":
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
    st.dataframe(df, use_container_width=True)

    st.plotly_chart(px.bar(df, x="Título", y="Precio"), use_container_width=True)
    st.plotly_chart(px.scatter(df, x="Precio", y="Ventas", hover_data=["Título"]), use_container_width=True)

    csv = df.to_csv(index=False)
    st.download_button("📥 Descargar CSV", csv, "ranking_ml.csv", "text/csv")
