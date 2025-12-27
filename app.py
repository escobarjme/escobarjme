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
    """Obtiene detalles profundos de PRODUCT (Catálogo) o ITEM (Publicación)"""
    headers = {"Authorization": f"Bearer {token}"}
    
    if obj_type == "PRODUCT":
        # Consultamos Catálogo
        r = requests.get(f"{API_BASE}/products/{obj_id}", headers=headers, timeout=15)
        if r.status_code == 200:
            p_data = r.json()
            # Buscamos el ganador de la oferta principal (Buy Box)
            winner = p_data.get("buy_box_winner")
            if winner:
                return {
                    "title": p_data.get("name"),
                    "price": winner.get("price"),
                    "sold_quantity": p_data.get("sold_quantity", 0),
                    "permalink": winner.get("permalink")
                }
            return {
                "title": p_data.get("name"),
                "price": None,
                "sold_quantity": p_data.get("sold_quantity", 0),
                "permalink": f"https://www.mercadolibre.com.ar/p/{obj_id}"
            }
    else:
        # Consultamos Publicación directa
        r = requests.get(f"{API_BASE}/items/{obj_id}", headers=headers, timeout=15)
        if r.status_code == 200:
            i_data = r.json()
            return {
                "title": i_data.get("title"),
                "price": i_data.get("price"),
                "sold_quantity": i_data.get("sold_quantity", 0),
                "permalink": i_data.get("permalink")
            }
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
    st.info("👋 Bienvenido. Para ver los datos actualizados, por favor inicia sesión.")
    st.link_button("🔐 Iniciar sesión con MercadoLibre", f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}")
    st.stop()

token = st.session_state["access_token"]

with st.sidebar:
    st.header("Filtros de Búsqueda")
    cat_name = st.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.slider("Cantidad de productos", 5, 50, 10)
    btn_buscar = st.button("🔍 Buscar más vendidos")

if btn_buscar:
    with st.spinner(f"Analizando ranking de {cat_name}..."):
        results = []
        highlights = get_highlights(token, CATEGORIES[cat_name])
        
        progress = st.progress(0)
        items_to_process = highlights[:limit]
        
        for i, h in enumerate(items_to_process):
            obj_id = h.get("id")
            obj_type = h.get("type")
            
            detail = get_any_detail(token, obj_id, obj_type)
            
            if detail:
                results.append({
                    "Posición": h.get("position", i+1),
                    "Título": detail.get("title"),
                    "Precio": detail.get("price"),
                    "Ventas": detail.get("sold_quantity"),
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
    
    # Formatear la tabla para mostrar el link como URL clickable en Streamlit
    st.dataframe(
        df,
        column_config={
            "Link": st.column_config.LinkColumn("Enlace Producto"),
            "Precio": st.column_config.NumberColumn("Precio ($)", format="$ %.2f"),
            "Ventas": st.column_config.NumberColumn("Ventas Totales")
        },
        use_container_width=True,
        hide_index=True
    )
    
    col_dl, col_cl = st.columns([1, 4])
    with col_dl:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Descargar CSV", csv, f"ranking_{st.session_state['last_category']}.csv", "text/csv")
    with col_cl:
        if st.button("🗑️ Limpiar Resultados"):
            st.session_state["data"] = []
            st.rerun()
else:
    st.info("Configura los filtros a la izquierda y presiona 'Buscar'.")
