import os
import requests
import streamlit as st
import pandas as pd

# =====================
# CONFIG STREAMLIT
# =====================
st.set_page_config(
    page_title="MercadoLibre Argentina – Más Vendidos",
    layout="wide"
)

API_BASE = "https://api.mercadolibre.com"
SITE_ID = "MLA"

# Variables de Entorno (Deben estar configuradas en Railway)
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
TOKEN_URL = f"{API_BASE}/oauth/token"

# Diccionario de Categorías con IDs corregidos
CATEGORIES = {
    "Accesorios para Vehículos": "MLA5725",
    "Repuestos Autos y Camionetas": "MLA1747",
    "Motor (Repuestos)": "MLA22262",
    "Notebooks": "MLA1652",
    "Zapatillas": "MLA109027",
}

# =====================
# SESSION STATE
# =====================
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "data" not in st.session_state:
    st.session_state.data = []
if "last_cat" not in st.session_state:
    st.session_state.last_cat = None

# =====================
# API FUNCTIONS
# =====================
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
        return r.json().get("access_token") if r.status_code == 200 else None
    except Exception:
        return None

@st.cache_data(ttl=300)
def get_any_data(token, category_id, limit=20):
    headers = {"Authorization": f"Bearer {token}"}
    
    # ESTRATEGIA 1: Intentar Highlights (Ranking oficial de ML)
    try:
        url_h = f"{API_BASE}/highlights/{SITE_ID}/category/{category_id}"
        r_h = requests.get(url_h, headers=headers, timeout=10)
        if r_h.status_code == 200 and r_h.json().get("content"):
            return r_h.json().get("content")[:limit]
    except Exception:
        pass

    # ESTRATEGIA 2: Fallback a Search (Búsqueda por ventas para subcategorías)
    try:
        url_s = f"{API_BASE}/sites/{SITE_ID}/search?category={category_id}&sort=sold_quantity_desc&limit={limit}"
        r_s = requests.get(url_s, headers=headers, timeout=10)
        if r_s.status_code == 200:
            results = r_s.json().get("results", [])
            return [{"id": x["id"], "type": "ITEM"} for x in results]
    except Exception:
        pass
    
    return []

def get_item_details(token, item_id):
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = requests.get(f"{API_BASE}/items/{item_id}", headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {
                "title": data.get("title"),
                "price": data.get("price"),
                "sold_quantity": data.get("sold_quantity", "Privado"),
                "permalink": data.get("permalink")
            }
    except Exception:
        return None
    return None

# =====================
# UI E INTERFAZ
# =====================
st.title("🛒 MercadoLibre Argentina – Más Vendidos")

# Verificación de credenciales
if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Faltan variables de entorno en Railway (CLIENT_ID, CLIENT_SECRET o REDIRECT_URI)")
    st.stop()

# Manejo de OAuth Callback
if "code" in st.query_params and not st.session_state.access_token:
    token = exchange_code_for_token(st.query_params["code"])
    if token:
        st.session_state.access_token = token
        st.query_params.clear()
        st.rerun()

# Login si no hay token
if not st.session_state.access_token:
    st.link_button(
        "🔐 Login con MercadoLibre",
        f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    )
    st.stop()

token = st.session_state.access_token

# =====================
# SIDEBAR (DEFINICIÓN DE VARIABLES)
# =====================
with st.sidebar:
    st.header("Configuración")
    cat_name = st.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.slider("Cantidad de productos", 5, 50, 20)
    # Definimos 'buscar' ANTES de usarlo en el flujo principal
    buscar = st.button("🔍 Buscar más vendidos")

# =====================
# LÓGICA DE BÚSQUEDA
# =====================
if buscar:
    with st.spinner("Conectando con la API de Mercado Libre..."):
        raw_items = get_any_data(token, CATEGORIES[cat_name], limit)
        
        if not raw_items:
            st.error(f"No se encontraron datos para {cat_name}. Prueba con otra categoría.")
        else:
            final_results = []
            progress_bar = st.progress(0)
            
            for i, raw in enumerate(raw_items):
                detail = get_item_details(token, raw["id"])
                if detail:
                    final_results.append({
                        "Posición": i + 1,
                        "Título": detail["title"],
                        "Precio": detail["price"],
                        "Vendidos": detail["sold_quantity"],
                        "Link": detail["permalink"]
                    })
                progress_bar.progress((i + 1) / len(raw_items))
            
            st.session_state.data = final_results
            st.session_state.last_cat = cat_name
            st.rerun()

# =====================
# MOSTRAR RESULTADOS
# =====================
if st.session_state.data:
    st.subheader(f"Resultados para: {st.session_state.last_cat}")
    df = pd.DataFrame(st.session_state.data)

    st.dataframe(
        df,
        column_config={
            "Precio": st.column_config.NumberColumn("Precio ($)", format="$ %.2f"),
            "Vendidos": st.column_config.TextColumn("Ventas (Estimado)"),
            "Link": st.column_config.LinkColumn("Ver en ML")
        },
        use_container_width=True,
        hide_index=True
    )

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Descargar CSV", csv, f"ranking_{st.session_state.last_cat}.csv", "text/csv")

    if st.button("Limpiar resultados"):
        st.session_state.data = []
        st.rerun()
