import streamlit as st
import requests
import pandas as pd

# =========================
# CONFIG GENERAL
# =========================
st.set_page_config(page_title="MercadoLibre – Más Vendidos", layout="wide")

SITE_ID = "MLA"

CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]

# =========================
# HEADERS (ANTI 403 Railway)
# =========================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-AR,es;q=0.9,en;q=0.8",
    "Referer": "https://www.mercadolibre.com.ar/",
    "Origin": "https://www.mercadolibre.com.ar",
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


def get_fallback_best_sellers(token, category_id, limit):
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


def get_item(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = {**HEADERS, "Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return None
    return r.json()


def build_record(item, position):
    return {
        "Ranking": position,
        "Título": item.get("title"),
        "Precio": item.get("price"),
        "Vendidos": item.get("sold_quantity"),
        "Link": item.get("permalink"),
    }


# =========================
# UI
# =========================
st.sidebar.title("Filtros")
st.sidebar.write("SITE_ID:", SITE_ID)

# =========================
# LOGIN FLOW
# =========================
params = st.query_params

if "code" not in params and "access_token" not in st.session_state:
    auth_url = (
        "https://auth.mercadolibre.com.ar/authorization"
        f"?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    st.markdown(f"[🔐 Login con MercadoLibre]({auth_url})")
    st.stop()

if "access_token" not in st.session_state:
    try:
        st.session_state["access_token"] = exchange_code_for_token(
            params["code"]
        )
        st.success("🔓 Autenticado correctamente")
    except Exception as e:
        st.error("Error en autenticación")
        st.exception(e)
        st.stop()

token = st.session_state["access_token"]

# =========================
# CATEGORIES
# =========================
categories = get_categories()

if not categories:
    st.error("❌ No se pudieron cargar las categorías (bloqueo de API)")
    st.stop()

category_map = {c["name"]: c["id"] for c in categories}

category_name = st.sidebar.selectbox(
    "Categoría", sorted(category_map.keys())
)

limit = st.sidebar.slider("Cantidad", 5, 20, 10)

st.title("🛒 MercadoLibre Argentina – Más Vendidos")

# =========================
# DATA LOAD
# =========================
with st.spinner("Cargando productos..."):
    category_id = category_map[category_name]

    highlights = get_highlights(token, category_id)
    records = []

    if highlights:
        for h in highlights[:limit]:
            if h.get("type") == "ITEM":
                item = get_item(token, h["id"])
                if item:
                    records.append(build_record(item, h["position"]))
    else:
        fallback = get_fallback_best_sellers(token, category_id, limit)
        for idx, item in enumerate(fallback, start=1):
            records.append(build_record(item, idx))

# =========================
# OUTPUT
# =========================
if not records:
    st.warning("No se encontraron datos para esta categoría.")
else:
    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True)
