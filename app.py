import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px

# =====================
# Configuración
# =====================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

SITE_ID = "MLA"  # MercadoLibre Argentina

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Faltan variables de entorno (CLIENT_ID / CLIENT_SECRET / REDIRECT_URI)")
    st.stop()

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

# =====================
# Session State
# =====================
st.session_state.setdefault("access_token", None)
st.session_state.setdefault("data", [])

# =====================
# OAuth
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
        st.error("❌ Error obteniendo token")
        st.text(r.text)
        return None

    return r.json().get("access_token")

# =====================
# MercadoLibre API
# =====================
@st.cache_data(ttl=86400)
def get_categories():
    url = f"https://api.mercadolibre.com/sites/{SITE_ID}/categories"

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)

        if r.status_code != 200:
            return []

        data = r.json()
        return data if isinstance(data, list) else []

    except Exception:
        return []

@st.cache_data(ttl=3600)
def get_best_sellers(token, category_id):
    url = f"https://api.mercadolibre.com/highlights/{SITE_ID}/category/{category_id}"
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}

    r = requests.get(url, headers=headers, timeout=10)

    if r.status_code != 200:
        return []

    return r.json().get("content", [])

def get_item(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}

    r = requests.get(url, headers=headers, timeout=10)
    return r.json() if r.status_code == 200 else None

def get_item_visits(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}/visits/time_window"
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    params = {"last": 30, "unit": "day"}

    r = requests.get(url, headers=headers, params=params, timeout=10)
    return r.json().get("total_visits", 0) if r.status_code == 200 else 0

def get_item_rating(token, item_id):
    url = f"https://api.mercadolibre.com/reviews/item/{item_id}"
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}

    r = requests.get(url, headers=headers, timeout=10)

    if r.status_code != 200:
        return None

    data = r.json()
    return data.get("rating_average")

def fetch_product_data(token, item, position):
    return {
        "Posición": position,
        "Título": item["title"],
        "Precio": item["price"],
        "Ventas": item.get("sold_quantity", 0),
        "Visitas 30d": get_item_visits(token, item["id"]),
        "Rating": get_item_rating(token, item["id"]),
        "Link": item["permalink"],
    }

# =====================
# UI
# =====================
st.set_page_config("MercadoLibre Argentina – Más Vendidos", "🛒", layout="wide")
st.title("🛒 MercadoLibre Argentina – Productos Más Vendidos")

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

if not categories:
    st.error("❌ No se pudieron cargar las categorías")
    st.stop()

cat_map = {c["name"]: c["id"] for c in categories}

st.sidebar.header("Filtros")
category = st.sidebar.selectbox("Categoría", sorted(cat_map.keys()))
limit = st.sidebar.slider("Cantidad de productos", 5, 20, 10)

if st.sidebar.button("🔍 Buscar"):
    with st.spinner("Consultando más vendidos..."):
        highlights = get_best_sellers(token, cat_map[category])

        records = []
        for h in highlights[:limit]:
            if h.get("type") == "ITEM":
                item = get_item(token, h["id"])
                if item:
                    records.append(fetch_product_data(token, item, h["position"]))

        st.session_state["data"] = records

# =====================
# Resultados
# =====================
if st.session_state["data"]:
    df = pd.DataFrame(st.session_state["data"])

    st.subheader("📊 Resultados")
    st.dataframe(df, use_container_width=True)

    st.plotly_chart(
        px.bar(df, x="Título", y="Precio", title="Precio por producto"),
        use_container_width=True,
    )

    st.plotly_chart(
        px.scatter(df, x="Precio", y="Ventas", hover_data=["Título"],
                   title="Precio vs Ventas"),
        use_container_width=True,
    )

    st.download_button(
        "📥 Descargar CSV",
        df.to_csv(index=False),
        "ranking_ml.csv",
        "text/csv",
    )
