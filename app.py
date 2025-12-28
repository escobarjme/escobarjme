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

CATEGORIES = {
    "Televisores": "MLA1002",
    "Celulares": "MLA1055",
    "Notebooks": "MLA1652",
    "Zapatillas": "MLA109027",
}

# =====================
# SESSION STATE
# =====================
for key in ["access_token", "data", "last_cat"]:
    st.session_state.setdefault(key, None if key == "access_token" else [])

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
    r = requests.get(
        f"{API_BASE}/highlights/{SITE_ID}/category/{category_id}",
        headers=headers,
        timeout=15
    )
    return r.json().get("content", []) if r.status_code == 200 else []


@st.cache_data(ttl=300)
def get_item(token, item_id):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_BASE}/items/{item_id}", headers=headers, timeout=15)
    return r.json() if r.status_code == 200 else None


@st.cache_data(ttl=300)
def get_best_item_from_product(token, product_id):
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(f"{API_BASE}/products/{product_id}", headers=headers, timeout=15)
    if r.status_code != 200:
        return None

    product = r.json()
    best_item = None
    max_sold = -1

    for item_id in product.get("items", []):
        item = get_item(token, item_id)
        if not item:
            continue

        sold = item.get("sold_quantity", 0)
        if sold > max_sold:
            max_sold = sold
            best_item = item

    if not best_item:
        return None

    brand = None
    for attr in best_item.get("attributes", []):
        if attr.get("id") == "BRAND":
            brand = attr.get("value_name")

    return {
        "title": best_item.get("title"),
        "price": best_item.get("price"),
        "sold_quantity": best_item.get("sold_quantity", 0),
        "brand": brand,
        "permalink": best_item.get("permalink"),
    }


# =====================
# UI
# =====================
st.title("🛒 MercadoLibre Argentina – Más Vendidos")

# OAuth callback
if "code" in st.query_params and not st.session_state.access_token:
    token = exchange_code_for_token(st.query_params["code"])
    if token:
        st.session_state.access_token = token
        st.query_params.clear()
        st.rerun()

# Login
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

    st.markdown("### 💰 Rango de precio")
    min_price = st.number_input("Mínimo", value=0)
    max_price = st.number_input("Máximo", value=10_000_000)

    buscar = st.button("🔍 Buscar")

# =====================
# DATA LOAD
# =====================
if buscar:
    with st.spinner("Extrayendo datos..."):
        results = []
        highlights = get_highlights(token, CATEGORIES[cat_name])[:limit]

        progress = st.progress(0.0)

        for i, h in enumerate(highlights):
            if h.get("type") == "PRODUCT":
                detail = get_best_item_from_product(token, h["id"])
            else:
                detail = get_item(token, h["id"])

            if detail and detail.get("price") is not None:
                if min_price <= detail["price"] <= max_price:
                    results.append({
                        "Posición": h.get("position", i + 1),
                        "Título": detail["title"],
                        "Marca": detail.get("brand"),
                        "Precio": detail["price"],
                        "Vendidos": detail["sold_quantity"],
                        "Link": detail["permalink"]
                    })

            progress.progress((i + 1) / len(highlights))

        st.session_state.data = results
        st.session_state.last_cat = cat_name
        st.rerun()

# =====================
# RESULTS
# =====================
if st.session_state.data:
    df = pd.DataFrame(st.session_state.data)

    # Métricas
    col1, col2, col3 = st.columns(3)
    col1.metric("Productos", len(df))
    col2.metric("Precio promedio", f"$ {df['Precio'].mean():,.0f}")
    col3.metric("Total vendidos", int(df["Vendidos"].sum()))

    st.subheader(f"Resultados: {st.session_state.last_cat}")

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

    # =====================
    # AGRUPADO POR MARCA
    # =====================
    st.subheader("🏷️ Ranking por Marca")
    brand_df = (
        df.groupby("Marca", dropna=False)
        .agg(
            Productos=("Título", "count"),
            Vendidos=("Vendidos", "sum"),
            Precio_Promedio=("Precio", "mean")
        )
        .sort_values("Vendidos", ascending=False)
        .reset_index()
    )

    st.dataframe(brand_df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Descargar CSV", csv, "ranking_ml.csv", "text/csv")

    if st.button("Limpiar"):
        st.session_state.data = []
        st.rerun()
