import streamlit as st
import requests
import pandas as pd

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="MercadoLibre Argentina – Más Vendidos",
    layout="wide"
)

API_BASE = "https://api.mercadolibre.com"
SITE_ID = "MLA"

CATEGORIES = {
    "Televisores": "MLA1002",
    "Celulares": "MLA1055",
    "Notebooks": "MLA1652",
    "Zapatillas": "MLA109027",
}

# =========================
# AUTH
# =========================
def get_token():
    # ACCESS_TOKEN guardado en Railway / secrets
    return st.secrets["ACCESS_TOKEN"]

# =========================
# API CALLS
# =========================
@st.cache_data(ttl=300)
def get_highlights(token, category_id):
    url = f"{API_BASE}/highlights/{SITE_ID}/category/{category_id}"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        return []

    return r.json().get("content", [])


@st.cache_data(ttl=300)
def get_product(token, product_id):
    url = f"{API_BASE}/products/{product_id}"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code != 200:
        return None

    return r.json()


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
def format_item(item, position):
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
    with st.spinner("Consultando ranking..."):
        highlights = get_highlights(token, CATEGORIES[category_name])
        records = []

        for h in highlights[:limit]:
            product_id = h.get("id")
            position = h.get("position", 0)
            h_type = h.get("type")

            st.write(f"Procesando {h_type}: {product_id}")

            item_id = None

            # PRODUCT → ITEM
            if h_type == "PRODUCT":
                product = get_product(token, product_id)
                if product:
                    buy_box = product.get("buy_box_winner")
                    if buy_box:
                        item_id = buy_box.get("item_id")

            # ITEM directo (fallback)
            elif h_type == "ITEM":
                item_id = product_id

            if not item_id:
                continue

            item = get_item(token, item_id)
            if not item:
                continue

            if item.get("title") and item.get("price") is not None:
                records.append(format_item(item, position))

        if not records:
            st.warning("No se encontraron datos para esta categoría.")
        else:
            df = pd.DataFrame(records).sort_values("Posición")
            st.success(f"Productos cargados: {len(df)}")

            st.dataframe(df, use_container_width=True)

            st.bar_chart(df.set_index("Título")["Precio"])

            st.download_button(
                "⬇️ Descargar CSV",
                df.to_csv(index=False).encode("utf-8"),
                "ranking_ml.csv",
                "text/csv"
            )
