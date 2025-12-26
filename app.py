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
# Categorías válidas (HIJA)
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
# Mercado Libre API
# =====================
def get_best_sellers(token, category_id):
    url = f"https://api.mercadolibre.com/highlights/{SITE_ID}/category/{category_id}"
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get("content", [])

def get_best_sellers_fallback(token, category_id, limit):
    url = f"https://api.mercadolibre.com/sites/{SITE_ID}/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "category": category_id,
        "sort": "sold_quantity_desc",
        "limit": limit,
    }
    r = requests.get(url, headers=headers, params=params, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get("results", [])

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
st.set_page_config("MercadoLibre – Más Vendidos", "🛒", layout="wide")
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

        if highlights:
            for h in highlights[:limit]:
                if h.get("type") == "ITEM":
                    item = get_item(token, h["id"])
                    if item:
                        records.append(fetch_product_data(token, item, h["position"]))
        else:
            fallback = get_best_sellers_fallback(
                token, CATEGORIES[category_name], limit
            )
            for idx, item in enumerate(fallback, start=1):
                records.append(fetch_product_data(token, item, idx))

        if not records:
            st.warning("No se encontraron datos para esta categoría.")

        st.session_state["data"] = records

# =====================
# Resultados
# =====================
if st.session_state["data"]:
    df = pd.DataFrame(st.session_state["data"])

    st.subheader("📊 Ranking")
    st.dataframe(df, use_container_width=True)

    st.plotly_chart(px.bar(df, x="Título", y="Precio"), use_container_width=True)
    st.plotly_chart(
        px.scatter(df, x="Precio", y="Ventas", hover_data=["Título"]),
        use_container_width=True,
    )

    csv = df.to_csv(index=False)
    st.download_button("📥 Descargar CSV", csv, "ranking_ml.csv", "text/csv")
