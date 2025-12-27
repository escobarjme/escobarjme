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
    st.error("❌ Faltan variables de entorno en Railway")
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
if "last_category" not in st.session_state:
    st.session_state["last_category"] = None

# =====================
# OAUTH & API
# =====================
def exchange_code_for_token(code):
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=15)
    return r.json().get("access_token") if r.status_code == 200 else None

@st.cache_data(ttl=300)
def get_highlights(token, category_id):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_BASE}/highlights/{SITE_ID}/category/{category_id}", headers=headers, timeout=15)
    return r.json().get("content", []) if r.status_code == 200 else []

@st.cache_data(ttl=300)
def get_item_detail(token, item_id):
    headers = {"Authorization": f"Bearer {token}"}
    # Intentamos primero como item, si no como product
    r = requests.get(f"{API_BASE}/items/{item_id}", headers=headers, timeout=15)
    if r.status_code == 200:
        return r.json()
    return None

# =====================
# UI
# =====================
st.title("🛒 MercadoLibre Argentina – Más Vendidos")

# Manejo de OAuth
if "code" in st.query_params and not st.session_state["access_token"]:
    token = exchange_code_for_token(st.query_params["code"])
    if token:
        st.session_state["access_token"] = token
        st.query_params.clear()
        st.rerun()

if not st.session_state["access_token"]:
    st.link_button("🔐 Login con MercadoLibre", f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}")
    st.stop()

token = st.session_state["access_token"]

with st.sidebar:
    st.header("Filtros")
    cat_name = st.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.slider("Cantidad", 5, 50, 20)
    btn_buscar = st.button("🔍 Buscar")

if btn_buscar:
    with st.spinner("Procesando datos..."):
        results = []
        highlights = get_highlights(token, CATEGORIES[cat_name])
        
        if not highlights:
            st.error("No se obtuvo respuesta de la API de Highlights. Verifica los permisos de tu App en Mercado Libre.")
        
        progress = st.progress(0)
        for i, h in enumerate(highlights[:limit]):
            # Intentar obtener ID de item directamente o via producto
            target_id = h.get("id")
            
            # Buscamos detalle
            detail = get_item_detail(token, target_id)
            
            if detail:
                results.append({
                    "Posición": h.get("position", i+1),
                    "Título": detail.get("title"),
                    "Precio": detail.get("price"),
                    "Ventas": detail.get("sold_quantity"),
                    "Link": detail.get("permalink")
                })
            
            progress.progress((i + 1) / len(highlights[:limit]))
        
        # ACTUALIZACIÓN DE ESTADO
        st.session_state["data"] = results
        st.session_state["last_category"] = cat_name
        
        if not results:
            st.warning("Se procesaron los IDs pero no se pudo obtener el detalle de ningún producto.")
        else:
            st.rerun() # Forzamos recarga para asegurar que el estado se lea bien

# MOSTRAR TABLA
if st.session_state["data"]:
    st.subheader(f"Top Ventas: {st.session_state['last_category']}")
    df = pd.DataFrame(st.session_state["data"])
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.download_button("Descargar CSV", df.to_csv(index=False).encode('utf-8'), "datos.csv")
    
    if st.button("Limpiar"):
        st.session_state["data"] = []
        st.rerun()
else:
    st.info("Haz clic en 'Buscar' para cargar los datos.")
