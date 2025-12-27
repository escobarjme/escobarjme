import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px


st.write("Query params:", st.query_params)

if "code" in st.query_params:
    st.success(f"Código recibido: {st.query_params['code']}")

# =====================
# Configuración general
# =====================
st.set_page_config(
    page_title="MercadoLibre – Más Vendidos",
    page_icon="🛒",
    layout="wide"
)

# =====================
# Variables de entorno (Railway)
# =====================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SITE_ID = os.getenv("SITE_ID", "MLA")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Faltan variables de entorno en Railway")
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
st.session_state.setdefault("results", [])

# =====================
# OAuth
# =====================
def get_auth_url():
    return (
        f"{AUTH_URL}"
        f"?response_type=code"
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
        st.error("❌ Error al obtener access_token")
        st.code(r.text)
        return None
    return r.json().get("access_token")

# =====================
# API Mercado Libre
# =====================
def get_categories():
    url = f"https://api.mercadolibre.com/sites/{SITE_ID}/categories"
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return []
    return r.json()

def get_category_detail(category_id):
    url = f"https://api.mercadolibre.com/categories/{category_id}"
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()

def get_highlights(token, category_id):
    url = f"https://api.mercadolibre.com/highlights/{SITE_ID}/category/{category_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)

    if r.status_code == 404:
        return []
    if r.status_code != 200:
        return None

    return r.json().get("content", [])

def get_item(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()

# =====================
# UI
# =====================
st.title("🛒 MercadoLibre Argentina – Más Vendidos")

# ===== OAuth callback =====
params = st.query_params
if "code" in params and not st.session_state["access_token"]:
    token = exchange_code_for_token(params["code"])
    if token:
        st.session_state["access_token"] = token
        st.query_params.clear()
        st.rerun()

# ===== Login =====
if not st.session_state["access_token"]:
    st.info("Iniciá sesión para continuar")
    st.link_button("🔐 Login con MercadoLibre", get_auth_url())
    st.stop()

token = st.session_state["access_token"]

# =====================
# Sidebar – Filtros
# =====================
st.sidebar.header("Filtros")

categories = get_categories()
if not categories:
    st.error("❌ No se pudieron cargar las categorías")
    st.stop()

cat_map = {c["name"]: c["id"] for c in categories}
category_name = st.sidebar.selectbox("Categoría", sorted(cat_map.keys()))

category_id = cat_map[category_name]
category_detail = get_category_detail(category_id)

subcat_id = category_id
if category_detail and category_detail.get("children_categories"):
    subcats = {
        c["name"]: c["id"]
        for c in category_detail["children_categories"]
    }
    subcat_name = st.sidebar.selectbox(
        "Subcategoría (opcional)",
        ["Todas"] + list(subcats.keys())
    )
    if subcat_name != "Todas":
        subcat_id = subcats[subcat_name]

limit = st.sidebar.slider("Cantidad", 5, 20, 10)

# =====================
# Buscar
# =====================
if st.sidebar.button("🔍 Buscar más vendidos"):
    with st.spinner("Consultando ranking..."):
        highlights = get_highlights(token, subcat_id)

        if highlights is None:
            st.error("❌ Error consultando Mercado Libre")
            st.stop()

        if not highlights:
            st.warning("Esta categoría no tiene ranking de más vendidos.")
            st.session_state["results"] = []
        else:
            rows = []
            for h in highlights[:limit]:
                if h["type"] != "ITEM":
                    continue
                item = get_item(token, h["id"])
                if not item:
                    continue
                rows.append({
                    "Posición": h["position"],
                    "Título": item["title"],
                    "Precio": item["price"],
                    "Ventas": item.get("sold_quantity"),
                    "Link": item["permalink"]
                })

            st.session_state["results"] = rows

# =====================
# Resultados
# =====================
if st.session_state["results"]:
    df = pd.DataFrame(st.session_state["results"])
    st.subheader("📊 Ranking de más vendidos")
    st.dataframe(df, use_container_width=True)

    st.plotly_chart(
        px.bar(df, x="Título", y="Precio", title="Precio por producto"),
        use_container_width=True
    )

    st.plotly_chart(
        px.scatter(df, x="Precio", y="Ventas", hover_data=["Título"],
                   title="Precio vs Ventas"),
        use_container_width=True
    )

    csv = df.to_csv(index=False)
    st.download_button(
        "📥 Descargar CSV",
        csv,
        "mas_vendidos_ml.csv",
        "text/csv"
    )
