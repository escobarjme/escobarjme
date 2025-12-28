import os
import requests
import streamlit as st
import pandas as pd

# =====================
# CONFIG STREAMLIT
# =====================
st.set_page_config(page_title="ML Ranking Pro", layout="wide")

API_BASE = "https://api.mercadolibre.com"
SITE_ID = "MLA"

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

# IDs de Categorías
CATEGORIES = {
    "Accesorios para Vehículos": "MLA5725",
    "Repuestos Autos y Camionetas": "MLA1747",
    "Motor (Repuestos)": "MLA22262",
    "Notebooks": "MLA1652",
    "Zapatillas": "MLA109027",
}

if "access_token" not in st.session_state:
    st.session_state.access_token = None

# =====================
# FUNCIONES API
# =====================
def get_token(code):
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post(f"{API_BASE}/oauth/token", data=payload)
    return r.json().get("access_token")

def fetch_data(token, cat_id, limit):
    headers = {"Authorization": f"Bearer {token}"}
    
    # Intentar Búsqueda Directa (Más fiable que Highlights en 2025)
    url = f"{API_BASE}/sites/{SITE_ID}/search?category={cat_id}&sort=sold_quantity_desc&limit={limit}"
    res = requests.get(url, headers=headers)
    
    if res.status_code != 200:
        st.error(f"Error API ML: {res.status_code} - {res.text}")
        return []
        
    items = res.json().get("results", [])
    results = []
    
    for i, item in enumerate(items):
        # En el search ya vienen los datos básicos, no necesitamos llamar a /items uno por uno
        # Esto evita bloqueos por exceso de peticiones
        results.append({
            "Posición": i + 1,
            "Título": item.get("title"),
            "Precio": item.get("price"),
            "Condición": item.get("condition"),
            "Link": item.get("permalink")
        })
    return results

# =====================
# INTERFAZ
# =====================
st.title("🛒 ML Argentina: Ranking de Ventas")

# Manejo de Auth
if "code" in st.query_params:
    st.session_state.access_token = get_token(st.query_params["code"])
    st.query_params.clear()
    st.rerun()

if not st.session_state.access_token:
    st.link_button("🔐 Conectar con Mercado Libre", 
                   f"https://auth.mercadolibre.com.ar/authorization?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}")
    st.stop()

# Dashboard
with st.sidebar:
    cat_sel = st.selectbox("Selecciona Categoría", list(CATEGORIES.keys()))
    cant = st.slider("Cantidad", 5, 50, 20)
    btn = st.button("🚀 Obtener Ranking")

if btn:
    with st.spinner("Consultando a Mercado Libre..."):
        data = fetch_data(st.session_state.access_token, CATEGORIES[cat_sel], cant)
        if data:
            df = pd.DataFrame(data)
            st.success(f"Se encontraron {len(df)} productos.")
            st.dataframe(df, use_container_width=True)
            st.download_button("Descargar CSV", df.to_csv(index=False), "ranking.csv")
        else:
            st.warning("La API no devolvió resultados. Revisa los logs arriba.")
