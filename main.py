import streamlit as st
import requests
import pandas as pd
from datetime import datetime
import plotly.express as px
import json
from groq import Groq

# ========== CREDENCIALES DESDE secrets.toml ==========
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

# Cliente Groq
client = Groq(api_key=GROQ_API_KEY)

# ========== CATEGORÍAS (puedes ampliarlas) ==========
CATEGORIES = {
    "Electrónica": "MLA35201",
    "Computadoras": "MLA1648",
    "Celulares": "MLA1051",
    "Hogar y Jardín": "MLA1574",
    "Herramientas": "MLA1500",
}

# ========== FLUJO DE LOGIN ==========
def redirect_to_login():
    auth_url = (
        "https://auth.mercadolibre.com.ar/authorization"
        f"?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    )
    st.markdown(f"[👉 Iniciar sesión en Mercado Libre]({auth_url})", unsafe_allow_html=True)

def exchange_code_for_token(code: str) -> str:
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    resp = requests.post(url, data=payload)
    resp.raise_for_status()
    return resp.json()["access_token"]

# ========== FUNCIONES UTILITARIAS PARA PRODUCTOS ==========
def get_top_products(token, category_id, limit=20):
    url = "https://api.mercadolibre.com/sites/MLA/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"category": category_id, "sort": "sold_quantity_desc", "limit": limit}
    return requests.get(url, headers=headers, params=params).json()["results"]

def get_item_visits(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}/visits/time_window"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"last": 7, "unit": "day", "ending": datetime.now().strftime("%Y-%m-%d")}
    return requests.get(url, headers=headers, params=params).json().get("total_visits", "N/A")

def get_item_rating(token, item_id):
    url = f"https://api.mercadolibre.com/reviews/item/{item_id}"
    headers = {"Authorization": f"Bearer {token}"}
    data = requests.get(url, headers=headers).json()
    return (
        data.get("rating_average", "N/A"),
        data.get("reviews", []),
        data.get("rating_levels", {}),
    )

def get_seller_reputation(token, seller_id):
    url = f"https://api.mercadolibre.com/users/{seller_id}"
    headers = {"Authorization": f"Bearer {token}"}
    rep = requests.get(url, headers=headers).json().get("seller_reputation", {})
    tx = rep.get("transactions", {})
    return {
        "level_id": rep.get("level_id", "N/A"),
        "power_seller_status": rep.get("power_seller_status", "N/A"),
        "transactions_total": tx.get("total", "N/A"),
    }

def format_rating_levels(levels):
    return (
        f"⭐ {levels.get('one_star',0)} | "
        f"⭐⭐ {levels.get('two_star',0)} | "
        f"⭐⭐⭐ {levels.get('three_star',0)} | "
        f"⭐⭐⭐⭐ {levels.get('four_star',0)} | "
        f"⭐⭐⭐⭐⭐ {levels.get('five_star',0)}"
    )

def fetch_product_data(token, product):
    item_id = product["id"]
    visits = get_item_visits(token, item_id)
    rating, reviews, levels = get_item_rating(token, item_id)
    seller = get_seller_reputation(token, product["seller"]["id"])
    return {
        "Título": product.get("title"),
        "Precio": product.get("price"),
        "Disponibles": product.get("available_quantity"),
        "Condición": product.get("condition", "").capitalize(),
        "Visitas": visits,
        "Rating": rating,
        "Reseñas": len(reviews),
        "Distribución Rating": format_rating_levels(levels),
        "Nivel Vendedor": seller["level_id"],
        "Power Seller": seller["power_seller_status"],
        "Transacciones": seller["transactions_total"],
        "Enlace": product.get("permalink"),
    }

# ========== GENERAR RESUMEN CON GROQ ==========
def generate_summary(records, model, max_tokens):
    prompt = f"""
    Analiza estos productos y resume:
    {json.dumps(records, indent=2)}
    Incluye principales hallazgos, precios y reputación de vendedores.
    """
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        stream=True,
    )
    for chunk in completion:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

# ========== APP PRINCIPAL ==========
def main():
    st.set_page_config("MercadoLibre Explorer", "🛒", layout="wide")
    st.title("🛒 MercadoLibre Explorer")

    # ----- Autenticación -----
    if "access_token" not in st.session_state:
        params = st.query_params
        if "code" not in params:
            st.info("Iniciá sesión para continuar.")
            redirect_to_login()
            st.stop()
        try:
            code = params["code"]
            st.session_state["access_token"] = exchange_code_for_token(code)
            st.query_params.clear()   # limpia la URL
            st.rerun()
        except Exception as e:
            st.error(f"Error al autenticar: {e}")
            st.stop()

    token = st.session_state["access_token"]

    # ----- Controles -----
    st.sidebar.header("Opciones")
    cat = st.sidebar.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.sidebar.slider("Cantidad de productos", 5, 30, 10)
    model = st.sidebar.selectbox("Modelo Groq", ["llama3-70b-8192", "mixtral-8x7b-32768"])
    max_tokens = st.sidebar.slider("Máx tokens", 512, 8192, 2048, step=512)

    if st.sidebar.button("🔍 Buscar productos"):
        with st.spinner("Cargando productos..."):
            raw_products = get_top_products(token, CATEGORIES[cat], limit)
            st.session_state["data"] = [fetch_product_data(token, p) for p in raw_products]

    # ----- Visualizaciones -----
    if "data" in st.session_state:
        df = pd.DataFrame(st.session_state["data"])
        st.subheader(f"Top {len(df)} en {cat}")
        st.dataframe(df, use_container_width=True)

        st.plotly_chart(px.bar(df, x="Título", y="Precio", title="Precios"), use_container_width=True)
        st.plotly_chart(px.pie(df, names="Condición", title="Condición"), use_container_width=True)

        if st.button("🧠 Generar resumen IA"):
            resumen = st.empty()
            texto = ""
            for chunk in generate_summary(df.to_dict("records"), model, max_tokens):
                texto += chunk
                resumen.markdown(texto)

# ========== EJECUCIÓN ==========
if __name__ == "__main__":
    main()

