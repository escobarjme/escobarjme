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
            st.error(f"❌ Error OAuth: {r.text}")
            return None
        return r.json().get("access_token")
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

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
query_params = st.query_params
if "code" in query_params and not st.session_state["access_token"]:
    code = query_params["code"]
    token = exchange_code_for_token(code)
    if token:
        st.session_state["access_token"] = token
        st.query_params.clear()
        st.rerun()

# Bloqueo si no hay login
if not st.session_state["access_token"]:
    st.info("Por favor, inicia sesión para acceder a los datos de la API.")
    st.link_button("🔐 Login con MercadoLibre", get_auth_url())
    st.stop()

token = st.session_state["access_token"]

# Sidebar para filtros
with st.sidebar:
    st.header("Filtros")
    category_name = st.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.slider("Cantidad de productos", 5, 50, 20)
    buscar = st.button("🔍 Buscar")

# Lógica de búsqueda
if buscar:
    with st.spinner(f"Consultando ranking de {category_name}..."):
        records = []
        highlights = get_highlights(token, CATEGORIES[category_name])
        
        # Barra de progreso para feedback visual
        progress_bar = st.progress(0)
        
        for idx, h in enumerate(highlights[:limit]):
            h_type = h.get("type")
            obj_id = h.get("id")
            position = h.get("position", idx + 1)

            item_id = None
            if h_type == "PRODUCT":
                product = get_product(token, obj_id)
                if product and "buy_box_winner" in product:
                    item_id = product["buy_box_winner"].get("item_id")
                elif product and "id" in product: # Fallback si no hay buybox
                    item_id = obj_id 
            else: # Tipo ITEM
                item_id = obj_id

            if item_id:
                item = get_item(token, item_id)
                if item and "title" in item:
                    records.append(format_item(item, position))
            
            progress_bar.progress((idx + 1) / len(highlights[:limit]))
        
        st.session_state["data"] = records
        st.session_state["last_category"] = category_name

# Mostrar Resultados si existen en el estado
if st.session_state["data"]:
    cat = st.session_state.get("last_category", "Seleccionada")
    st.subheader(f"Top {len(st.session_state['data'])} - {cat}")
    
    df = pd.DataFrame(st.session_state["data"]).sort_values("Posición")
    
    # Formatear precio para mejor visualización
    df_display = df.copy()
    df_display["Precio"] = df_display["Precio"].map("${:,.2f}".format)
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="⬇️ Descargar CSV",
            data=csv,
            file_name=f"ranking_ml_{cat.lower()}.csv",
            mime="text/csv",
        )
    with col2:
        if st.button("🗑️ Limpiar Resultados"):
            st.session_state["data"] = []
            st.rerun()
else:
    st.info("Usa el panel de la izquierda para buscar productos.")
