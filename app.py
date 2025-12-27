import os
import streamlit as st
import requests
import pandas as pd

# =========================
# CONFIG GENERAL
# =========================
st.set_page_config(page_title="MercadoLibre – Más Vendidos", layout="wide")

SITE_ID = "MLA"

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Faltan variables de entorno en Railway")
    st.stop()

# =========================
# HEADERS (ANTI 403)
# =========================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "es-AR,es;q=0.9",
    "Referer": "https://www.mercadolibre.com.ar/",
}

# =========================
# AUTH
# =========================
def exchange_code_for_token(code):
    url = "https://api.mercadolibre.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post(url, data=data, timeout=10)
    r.raise_for_status()
    return r.json()["access_token"]

# =========================
# API HELPERS
# =========================
@st.cache_data(show_spinner=False)
def get_categories():
    url = f"https://api.mercadolibre.com/sites/{SITE_ID}/categories"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return []
    return r.json()

def get_highlights(token, category_id):
    url = f"https://api.mercadolibre.com/highlights/{SITE_ID}/category/{category_id}"
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get("content", [])

def get_fallback(token, category_id, limit):
    url = f"https://api.mercadolibre.com/sites/{SITE_ID}/search"
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    params = {
        "category": category_id,
        "sort": "sold_quantity_desc",
        "limit": limit,
    }
    r = requests.get(url, headers=headers, params=params, timeout=10)
    if r.status_code != 200:
        return []
    return r.json().get("results", [])

def build_record(item, pos):
    return {
        "Ranking": pos,
        "Título": item.get("title"),
        "Precio": item.get("price"),
        "Vendidos": item.get("sold_quantity"),
        "Link": item.get("permalink"),
    }

# =========================
# LOGIN FLOW
# =========================
params = st.query_params

if "access_token" not in st.session_state:
    if "code" not in params:
        auth_url = (
            "https://auth.mercadolibre.com.ar/authorization"
            f"?response_type=code&client_id={CLIENT_ID}"
            f"&redirect_uri={REDIRECT_URI}"
        )
        st.markdown(f"[🔐 Login con MercadoLibre]({auth_url})")
        st.stop()
    else:
        st.session_state["access_token"] = exchange_code_for_token(params["code"])
        st.rerun()

token = st.session_state["access_token"]

# =========================
# UI
# =========================
st.sidebar.title("Filtros")
st.sidebar.write("SITE_ID:", SITE_ID)

categories = get_categories()

if not categories:
    st.error("❌ No se pudieron cargar las categorías")
    st.stop()

cat_map = {c["name"]: c["id"] for c in categories}

category = st.sidebar.selectbox("Categoría", sorted(cat_map.keys()))
limit = st.sidebar.slider("Cantidad", 5, 20, 10)

st.title("🛒 MercadoLibre Argentina – Más Vendidos")

with st.spinner("Cargando productos..."):
    cid = cat_map[category]
    data = []

    highlights = get_highlights(token, cid)

    if highlights:
        for h in highlights[:limit]:
            if h["type"] == "ITEM":
                item = requests.get(
                    f"https://api.mercadolibre.com/items/{h['id']}",
                    headers={**HEADERS, "Authorization": f"Bearer {token}"}
                ).json()
                data.append(build_record(item, h["position"]))
    else:
        fallback = get_fallback(token, cid, limit)
        for i, item in enumerate(fallback, start=1):
            data.append(build_record(item, i))

if not data:
    st.warning("No se encontraron datos para esta categoría.")
else:
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
