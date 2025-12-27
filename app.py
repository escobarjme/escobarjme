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
    st.error("❌ Faltan variables de entorno en Railway (CLIENT_ID, CLIENT_SECRET o REDIRECT_URI)")
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
if "access_token" not in st.session_state:
    st.session_state["access_token"] = None
if "data" not in st.session_state:
    st.session_state["data"] = []

# =====================
# OAUTH FUNCTIONS
# =====================
def get_auth_url():
    return (
        f"{AUTH_URL}?robot=false&response_type=code"
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
    try:
        r = requests.post(TOKEN_URL, data=payload, timeout=15)
        if r.status_code != 200:
            return None
        return r.json().get("access_token")
    except:
        return None

# =====================
# API CALLS
# =====================
@st.cache_data(ttl=300)
def get_highlights(token, category_id):
    url = f"{API_BASE}/highlights/{SITE_ID}/category/{category_id}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        return r.json().get("content", []) if r.status_code == 200 else []
    except:
        return []

@st.cache_data(ttl=300)
def get_product(token, product_id):
    try:
        r = requests.get(
            f"{API_BASE}/products/{product_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        return r.json() if r.status_code == 200 else None
    except:
        return None

@st.cache_data(ttl=300)
def get_item(token, item_id):
    try:
        r = requests.get(
            f"{API_BASE}/items/{item_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        return r.json() if r.status_code == 200 else None
    except:
        return None

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
# UI & LOGIC
# =====================
st.title("🛒 MercadoLibre Argentina – Más Vendidos")

# Manejo de OAuth Callback
if "code" in st.query_params and not st.session_state["access_token"]:
    token = exchange_code_for_token(st.query_params["code"])
    if token:
        st.session_state["access_token"] = token
        st.query_params.clear()
        st.rerun()

# Bloqueo si no hay login
if not st.session_state["access_token"]:
    st.info("Inicia sesión para consultar los productos más vendidos.")
    st.link_button("🔐 Login con MercadoLibre", get_auth_url())
    st.stop()

token = st.session_state["access_token"]

# Sidebar
with st.sidebar:
    st.header("Filtros")
    category_name = st.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.slider("Cantidad de productos", 5, 50, 20)
    buscar = st.button("🔍 Buscar")

# Lógica de búsqueda
if buscar:
    with st.spinner(f"Consultando ranking..."):
        records = []
        highlights = get_highlights(token, CATEGORIES[category_name])
        
        progress_bar = st.progress(0)
        
        for idx, h in enumerate(highlights[:limit]):
            h_type = h.get("type")
            obj_id = h.get("id")
            position = h.get("position", idx + 1)
            item_id = None

            if h_type == "PRODUCT":
                product_data = get_product(token, obj_id)
                # --- CORRECCIÓN CRÍTICA AQUÍ ---
                if product_data and isinstance(product_data, dict):
                    winner = product_data.get("buy_box_winner")
                    if isinstance(winner, dict):
                        item_id = winner.get("item_id")
                    
                    # Si no hay ganador de buybox, usamos el ID del producto como fallback
                    if not item_id:
                        item_id = obj_id 
            else:
                item_id = obj_id

            if item_id:
                item = get_item(token, item_id)
                if item and isinstance(item, dict) and item.get("title"):
                    records.append(format_item(item, position))
            
            progress_bar.progress((idx + 1) / len(highlights[:limit]))
        
        st.session_state["data"] = records
        st.session_state["last_category"] = category_name

# Renderizado de Tabla
if st.session_state["data"]:
    cat = st.session_state.get("last_category", "")
    st.subheader(f"Resultados: {cat}")
    
    df = pd.DataFrame(st.session_state["data"]).sort_values("Posición")
    
    # Formato visual
    df_display = df.copy()
    if "Precio" in df_display.columns:
        df_display["Precio"] = df_display["Precio"].apply(lambda x: f"$ {x:,.2f}" if x else "N/A")
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Descargar CSV", csv, f"ranking_{cat}.csv", "text/csv")
    
    if st.button("🗑️ Limpiar"):
        st.session_state["data"] = []
        st.rerun()
else:
    st.info("Haz clic en 'Buscar' para cargar los datos.")
