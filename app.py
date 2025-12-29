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

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Faltan variables de entorno en Railway")
    st.stop()

AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
TOKEN_URL = f"{API_BASE}/oauth/token"

# IDs Corregidos según tu consulta
CATEGORIES = {
    "Accesorios para Vehículos (Gral)": "MLA5725",
    "Repuestos Autos y Camionetas": "MLA3483",
    "Baterías": "MLA403348",
    "Neumáticos": "MLA22195",
    "Aceites para Motor": "MLA373901",
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
    r = requests.post(TOKEN_URL, data=payload, timeout=15)
    return r.json().get("access_token") if r.status_code == 200 else None

@st.cache_data(ttl=300)
def get_highlights(token, category_id):
    headers = {"Authorization": f"Bearer {token}"}
    # Intentar primero con Highlights
    r = requests.get(
        f"{API_BASE}/highlights/{SITE_ID}/category/{category_id}",
        headers=headers,
        timeout=15
    )
    
    if r.status_code == 200:
        return r.json().get("content", [])
    
    # FALLBACK: Si highlights falla, buscar por más vendidos (sort=sold_quantity_desc)
    st.warning(f"Nota: Usando búsqueda por relevancia para esta subcategoría...")
    r_search = requests.get(
        f"{API_BASE}/sites/{SITE_ID}/search?category={category_id}&sort=sold_quantity_desc",
        headers=headers,
        timeout=15
    )
    if r_search.status_code == 200:
        results = r_search.json().get("results", [])
        # Adaptar formato de búsqueda al formato de highlights
        return [{"id": x["id"], "type": "ITEM", "position": i+1} for i, x in enumerate(results)]
    
    return []

@st.cache_data(ttl=300)
def get_any_detail(token, obj_id, obj_type):
    headers = {"Authorization": f"Bearer {token}"}

    # Si es PRODUCT (Catálogo)
    if obj_type == "PRODUCT":
        r = requests.get(f"{API_BASE}/products/{obj_id}", headers=headers, timeout=15)
        if r.status_code != 200: return None
        product = r.json()
        items = product.get("items", [])
        if not items:
            return {
                "title": product.get("name"),
                "price": None,
                "sold_quantity": "N/A",
                "permalink": f"https://www.mercadolibre.com.ar/p/{obj_id}"
            }
        obj_id = items[0] # Usar el primer item del catálogo

    # ITEM directo
    r_item = requests.get(f"{API_BASE}/items/{obj_id}", headers=headers, timeout=15)
    if r_item.status_code == 200:
        item = r_item.json()
        return {
            "title": item.get("title"),
            "price": item.get("price"),
            "sold_quantity": item.get("sold_quantity", 0),
            "permalink": item.get("permalink")
        }
    return None

# =====================
# UI
# =====================
st.title("🛒 MercadoLibre Argentina – Más Vendidos")

if "code" in st.query_params and not st.session_state.access_token:
    token = exchange_code_for_token(st.query_params["code"])
    if token:
        st.session_state.access_token = token
        st.query_params.clear()
        st.rerun()

if not st.session_state.access_token:
    st.link_button(
        "🔐 Login con MercadoLibre",
        f"{AUTH_URL}?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    )
    st.stop()

token = st.session_state.access_token

# =====================
# SIDEBAR
# =====================
with st.sidebar:
    st.header("Filtros")
    cat_name = st.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.slider("Cantidad", 5, 50, 20)
    buscar = st.button("🔍 Buscar")

# =====================
# DATA LOAD
# =====================
if buscar:
    with st.spinner("Extrayendo datos..."):
        results = []
        highlights = get_highlights(token, CATEGORIES[cat_name])
        
        if not highlights:
            st.error("No se encontraron datos para esta categoría.")
        else:
            items = highlights[:limit]
            progress = st.progress(0.0)

            for i, h in enumerate(items):
                detail = get_any_detail(token, h.get("id"), h.get("type"))
                if detail:
                    results.append({
                        "Posición": h.get("position", i + 1),
                        "Título": detail["title"],
                        "Precio": detail["price"],
                        "Vendidos": detail["sold_quantity"],
                        "Link": detail["permalink"]
                    })
                progress.progress((i + 1) / len(items))

            st.session_state.data = results
            st.session_state.last_cat = cat_name
            st.rerun()

# =====================
# RESULTS
# =====================
if st.session_state.data:
    st.subheader(f"Resultados: {st.session_state.last_cat}")
    df = pd.DataFrame(st.session_state.data)

    st.dataframe(
        df,
        column_config={
            "Precio": st.column_config.NumberColumn("Precio ($)", format="$ %.2f"),
            "Vendidos": st.column_config.NumberColumn("Unidades Vendidas"),
            "Link": st.column_config.LinkColumn("Ver en ML")
        },
        use_container_width=True,
        hide_index=True
    )

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Descargar CSV", csv, "ranking_ml.csv", "text/csv")

    if st.button("Limpiar"):
        st.session_state.data = []
        st.rerun()
