import streamlit as st
import requests
import pandas as pd

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="MercadoLibre Argentina – Más Vendidos", layout="wide")

API_BASE = "https://api.mercadolibre.com"

CATEGORIES = {
    "Celulares": "MLA1055",
    "Electrónica": "MLA1002",
    "Computación": "MLA1648",
    "Hogar": "MLA1574",
}

# =========================
# AUTH
# =========================
def get_token():
    return st.secrets["ACCESS_TOKEN"]

# =========================
# API CALLS
# =========================
@st.cache_data(ttl=300)
def get_best_sellers(token, category_id):
    url = f"{API_BASE}/highlights/MLA/category/{category_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=15)

    if r.status_code != 200:
        return []

    return r.json().get("content", [])


@st.cache_data(ttl=300)
def get_item(token, item_id):
    url = f"{API_BASE}/items/{item_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=15)

    if r.status_code != 200:
        return None

    return r.json()


# =========================
# DATA FORMAT
# =========================
def fetch_product_data(item, position):
    return {
        "Posición": position,
        "ID": item.get("id"),
        "Título": item.get("title"),
        "Precio": item.get("price"),
        "Ventas": item.get("sold_quantity"),
        "Link": item.get("permalink"),
    }


# =========================
# UI
# =========================
st.title("🛒 MercadoLibre Argentina – Más Vendidos")

with st.sidebar:
    st.header("Filtros")
    category_name = st.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.slider("Cantidad de productos", 5, 50, 20)

token = get_token()

if st.sidebar.button("🔍 Buscar"):
    with st.spinner("Consultando ranking de Mercado Libre..."):
        highlights = get_best_sellers(token, CATEGORIES[category_name])
        records = []

        for h in highlights[:limit]:
            item_id = h.get("item_id")
            position = h.get("position", 0)

            if not item_id:
                continue

            st.write(f"Procesando ITEM: {item_id}")

            item = get_item(token, item_id)
            if not item:
                continue

            if item.get("title") and item.get("price") is not None:
                records.append(
                    fetch_product_data(item, position)
                )

        if not records:
            st.warning("No se encontraron datos para esta categoría.")
        else:
            df = pd.DataFrame(records).sort_values("Posición")
            st.success(f"Productos cargados: {len(df)}")

            st.dataframe(df, use_container_width=True)

            st.bar_chart(
                df.set_index("Título")["Precio"]
            )

            st.download_button(
                "⬇️ Descargar CSV",
                df.to_csv(index=False).encode("utf-8"),
                file_name="mas_vendidos_ml.csv",
                mime="text/csv",
            )
