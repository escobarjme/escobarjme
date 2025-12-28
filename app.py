import os
import requests
import streamlit as st
import pandas as pd  # <--- Corregido aquí

# =====================
# CONFIG STREAMLIT
# =====================
st.set_page_config(
    page_title="ML Ranking Argentina", 
    layout="wide",
    page_icon="🛒"
)

# IDs de Categorías verificados para Argentina (MLA)
CATEGORIES = {
    "Accesorios para Vehículos": "MLA5725",
    "Repuestos Autos y Camionetas": "MLA1747",
    "Motor (Repuestos)": "MLA22262",
    "Notebooks": "MLA1652",
    "Zapatillas": "MLA109027",
}

def fetch_ranking(cat_id, limit):
    # Endpoint de búsqueda filtrado por categoría y ordenado por cantidad de ventas
    url = f"https://api.mercadolibre.com/sites/MLA/search?category={cat_id}&sort=sold_quantity_desc&limit={limit}"
    
    # Headers para simular una petición de navegador y evitar bloqueos
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    
    try:
        # Petición pública (sin token para evitar el error 403 de permisos)
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            items = response.json().get("results", [])
            data = []
            for i, item in enumerate(items):
                data.append({
                    "Pos.": i + 1,
                    "Título": item.get("title"),
                    "Precio": item.get("price"),
                    "Condición": item.get("condition"),
                    "Link": item.get("permalink")
                })
            return data
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

# =====================
# INTERFAZ DE USUARIO
# =====================
st.title("🛒 Ranking de Ventas Mercado Libre")
st.markdown("""
Esta herramienta obtiene los productos **más vendidos** de una categoría utilizando la API pública de Mercado Libre. 
Ideal para análisis de mercado en tiempo real.
""")

with st.sidebar:
    st.header("Configuración")
    opcion = st.selectbox("Selecciona una Categoría", list(CATEGORIES.keys()))
    cantidad = st.slider("Cantidad de productos", 10, 50, 20)
    st.divider()
    boton = st.button("🚀 Obtener Ranking")

if boton:
    with st.spinner(f"Consultando los más vendidos de {opcion}..."):
        res = fetch_ranking(CATEGORIES[opcion], cantidad)
        
        if res:
            df = pd.DataFrame(res)
            
            # Formatear la tabla
            st.subheader(f"Top {len(df)}: {opcion}")
            
            st.dataframe(
                df, 
                column_config={
                    "Precio": st.column_config.NumberColumn("Precio ($)", format="$ %.2f"),
                    "Link": st.column_config.LinkColumn("Ver Producto")
                },
                use_container_width=True, 
                hide_index=True
            )
            
            # Botón de descarga
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="⬇️ Descargar Ranking en CSV",
                data=csv,
                file_name=f"ranking_{opcion.lower().replace(' ', '_')}.csv",
                mime="text/csv",
            )
        else:
            st.warning("No se pudieron obtener datos. Intenta de nuevo en unos segundos.")

# Pie de página
st.divider()
st.caption("Desarrollado para análisis de datos de Mercado Libre Argentina.")
