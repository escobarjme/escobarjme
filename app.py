import streamlit as st
import requests
import os

# ========================
# CONFIG
# ========================
SITE_ID = "MLA"
API_BASE = "https://api.mercadolibre.com"

st.set_page_config(page_title="MercadoLibre Argentina – Más Vendidos", layout="wide")

# ========================
# FUNCIONES
# ========================
@st.cache_data
def get_categories():
    url = f"{API_BASE}/sites/{SITE_ID}/categories"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

@st.cache_data
def get_subcategories(category_id):
    url = f"{API_BASE}/categories/{category_id}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json().get("children_categories", [])

@st.cache_data
def get_highlights(category_id):
    url = f"{API_BASE}/highlights/{SITE_ID}/category/{category_id}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json().get("content", [])

def get_items(item_ids):
    if not item_ids:
        return []

    ids = ",".join(item_ids)
    url = f"{API_BASE}/items?ids={ids}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()

    return [i["body"] for i in r.json() if i.get("code") == 200]

# ========================
# UI
# ========================
st.sidebar.title("Filtros")

st.sidebar.write("SITE_ID:", SITE_ID)

categories = get_categories()
category_map = {c["name"]: c["id"] for c in categories}

selected_category_name = st.sidebar.selectbox(
    "Categoría",
    list(category_map.keys())
)

selected_category_id = category_map[selected_category_name]

subcategories = get_subcategories(selected_category_id)
subcategory_map = {c["name"]: c["id"] for c in subcategories}

selected_subcategory_id = selected_category_id

if subcategory_map:
    selected_sub_name = st.sidebar.selectbox(
        "Subcategoría",
        list(subcategory_map.keys())
    )
    selected_subcategory_id = subcategory_map[selected_sub_name]

# ========================
# CONTENIDO
# ========================
st.title("🛒 MercadoLibre Argentina – Más Vendidos")

highlights = get_highlights(selected_subcategory_id)

if not highlights:
    st.warning("No se encontraron datos para esta categoría.")
    st.stop()

item_ids = [h["id"] for h in highlights if h["type"] == "ITEM"]

items = get_items(item_ids)

if not items:
    st.warning("No se pudieron cargar los productos.")
    st.stop()

cols = st.columns(4)

for idx, item in enumerate(items):
    with cols[idx % 4]:
        st.image(item.get("thumbnail"), use_container_width=True)
        st.subheader(item.get("title"))
        st.write(f"💰 ${item.get('price'):,}")
        st.write(f"🏷️ {item.get('condition', '').capitalize()}")
        st.markdown(f"[Ver en MercadoLibre]({item.get('permalink')})")
