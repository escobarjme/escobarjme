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
# FUNCIONES API
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
def get_any_detail(token, obj_id, obj_type):
    """Detecta si es PRODUCT o ITEM y consulta el endpoint correcto"""
    headers = {"Authorization": f"Bearer {token}"}
    
    if obj_type == "PRODUCT":
        # Primero intentamos obtener el producto para sacar el 'buy_box_winner' (el item real a la venta)
        r = requests.get(f"{API_BASE}/products/{obj_id}", headers=headers, timeout=15)
        if r.status_code == 200:
            p_data = r.json()
            winner = p_data.get("buy_box_winner")
            if winner and winner.get("item_id"):
                # Si hay ganador, consultamos ese item para tener precio y link real
                return get_any_detail(token, winner.get("item_id"), "ITEM")
            return p_data # Si no hay ganador, devolvemos el producto base
    else:
        # Consulta directa de ITEM
        r = requests.get(f"{API_BASE}/items/{obj_id}", headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
    return None

# =====================
# UI
# =====================
st.title("🛒 MercadoLibre Argentina – Más Vendidos")

# OAuth
if "code" in st.query_params and not st.session_state["access_token"]:
    token = exchange_code_for_token(st.query_params["code"])
    if token:
        st.session_state["access_token"] = token
        st.query_params.clear()
        st.rerun()

if not st.session_state["access_token"]:
    st.info("Por favor, inicia sesión.")
    st.link_button("🔐 Login con MercadoLibre", f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}")
    st.stop()

token = st.session_state["access_token"]

with st.sidebar:
    st.header("Filtros")
    cat_name = st.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.slider("Cantidad", 5, 50, 20)
    btn_buscar = st.button("🔍 Buscar")

if btn_buscar:
    with st.spinner("Obteniendo ranking y detalles..."):
        results = []
        highlights = get_highlights(token, CATEGORIES[cat_name])
        
        progress = st.progress(0)
        items_to_process = highlights[:limit]
        
        for i, h in enumerate(items_to_process):
            obj_id = h.get("id")
            obj_type = h.get("type") # IMPORTANTE: 'PRODUCT' o 'ITEM'
            
            detail = get_any_detail(token, obj_id, obj_type)
            
            if detail:
                results.append({
                    "Posición": h.get("position", i+1),
                    "Título": detail.get("name") if obj_type == "PRODUCT" and not detail.get("title") else detail.get("title"),
                    "Precio": detail.get("price"),
                    "Ventas": detail.get("sold_quantity", 0),
                    "Link": detail.get("permalink")
                })
            
            progress.progress((i + 1) / len(items_to_process))
        
        st.session_state["data"] = results
        st.session_state["last_category"] = cat_name
        st.rerun()

# MOSTRAR TABLA
if st.session_state["data"]:
    st.subheader(f"Top Ventas: {st.session_state['last_category']}")
    df = pd.DataFrame(st.session_state["data"])
    
    # Formatear precio para la vista
    df_display = df.copy()
    if "Precio" in df_display.columns:
        df_display["Precio"] = df_display["Precio"].map(lambda x: f"$ {x:,.2f}" if x else "N/A")

    st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    st.download_button("⬇️ Descargar CSV", df.to_csv(index=False).encode('utf-8'), f"ranking_{cat_name}.csv", "text/csv")
    
    if st.button("🗑️ Limpiar Resultados"):
        st.session_state["data"] = []
        st.rerun()
else:
    st.info("Selecciona una categoría y haz clic en 'Buscar'.")
