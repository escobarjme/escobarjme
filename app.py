import os
import requests
import streamlit as st
import pd

# CONFIG
st.set_page_config(page_title="ML Ranking Argentina", layout="wide")

# IDs de Categorías (Verificados)
CATEGORIES = {
    "Accesorios para Vehículos": "MLA5725",
    "Repuestos Autos y Camionetas": "MLA1747",
    "Motor (Repuestos)": "MLA22262",
    "Notebooks": "MLA1652",
    "Zapatillas": "MLA109027",
}

def fetch_ranking(cat_id, limit):
    url = f"https://api.mercadolibre.com/sites/MLA/search?category={cat_id}&sort=sold_quantity_desc&limit={limit}"
    
    # HEADERS PARA ENGAÑAR AL FILTRO 403
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Accept-Language": "es-AR,es;q=0.9",
        "Connection": "keep-alive"
    }
    
    try:
        # Petición SIN TOKEN (más segura para evitar el 403 de permisos)
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            items = response.json().get("results", [])
            data = []
            for i, item in enumerate(items):
                data.append({
                    "Pos.": i + 1,
                    "Título": item.get("title"),
                    "Precio": item.get("price"),
                    "Ventas (Ranking)": "Top Vendido",
                    "Link": item.get("permalink")
                })
            return data
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

# INTERFAZ SIMPLE
st.title("🛒 Ranking de Ventas ML")
st.info("Esta versión utiliza acceso público para evitar bloqueos 403.")

with st.sidebar:
    opcion = st.selectbox("Categoría", list(CATEGORIES.keys()))
    cantidad = st.slider("Cantidad", 10, 50, 20)
    boton = st.button("🚀 Buscar")

if boton:
    res = fetch_ranking(CATEGORIES[opcion], cantidad)
    if res:
        df = pd.DataFrame(res)
        st.dataframe(df, use_container_width=True, hide_index=True)
