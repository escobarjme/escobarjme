import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import json

# ====
# Variables de entorno
# ====
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")  # opcional

# ====
# URLs Mercado Libre
# ====
AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
ME_URL = "https://api.mercadolibre.com/users/me"

# ====
# Validaciones iniciales
# ====
if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Faltan variables de entorno: CLIENT_ID / CLIENT_SECRET / REDIRECT_URI")
    st.stop()

# ====
# Session State
# ====
if "access_token" not in st.session_state:
    st.session_state["access_token"] = None
if "data" not in st.session_state:
    st.session_state["data"] = []

# ====
# OAuth Helpers
# ====
def get_auth_url():
    return (
        f"{AUTH_URL}?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state=railway_{os.urandom(8).hex()}"
    )

def exchange_code_for_token(code: str):
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=10)
    if r.status_code != 200:
        st.error("❌ Error al obtener access_token")
        st.code(r.text)
        return None
    return r.json().get("access_token")

# ====
# Categorías MLA
# ====
CATEGORIES = {
    "Electrónica": "MLA35201",
    "Computadoras": "MLA1648",
    "Celulares": "MLA1051",
    "Hogar y Jardín": "MLA1574",
    "Herramientas": "MLA1500",
}

# ====
# Funciones MercadoLibre
# ====
def get_top_products(token, category_id, limit=20):
    url = "https://api.mercadolibre.com/sites/MLA/search"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"category": category_id, "sort": "sold_quantity_desc", "limit": limit}
    return requests.get(url, headers=headers, params=params).json().get("results", [])

def get_item_visits(token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}/visits/time_window"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"last": 30, "unit": "day", "ending": datetime.now().strftime("%Y-%m-%d")}
    r = requests.get(url, headers=headers, params=params)
    return r.json().get("total_visits", "N/A")

def get_item_rating(token, item_id):
    url = f"https://api.mercadolibre.com/reviews/item/{item_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return "N/A", [], {}
    data = r.json()
    return data.get("rating_average", "N/A"), data.get("reviews", []), data.get("rating_levels", {})

def get_seller_reputation(token, seller_id):
    url = f"https://api.mercadolibre.com/users/{seller_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        return {}
    data = r.json()
    rep = data.get("seller_reputation", {})
    transactions = rep.get("transactions", {})
    return {
        "level_id": rep.get("level_id", "N/A"),
        "power_seller_status": rep.get("power_seller_status", "N/A"),
        "transactions_total": transactions.get("total", "N/A"),
        "transactions_completed": transactions.get("completed", "N/A"),
        "transactions_canceled": transactions.get("canceled", "N/A"),
    }

def format_rating_levels(rating_levels):
    return (
        f"⭐: {rating_levels.get('one_star',0)} | "
        f"⭐⭐: {rating_levels.get('two_star',0)} | "
        f"⭐⭐⭐: {rating_levels.get('three_star',0)} | "
        f"⭐⭐⭐⭐: {rating_levels.get('four_star',0)} | "
        f"⭐⭐⭐⭐⭐: {rating_levels.get('five_star',0)}"
    )

def fetch_product_data(token, product):
    item_id = product["id"]
    rating, reviews, rating_levels = get_item_rating(token, item_id)
    seller_rep = get_seller_reputation(token, product["seller"]["id"])
    return {
        "Título": product.get("title"),
        "Precio": f"${product.get('price',0):,.0f}",
        "Condición": product.get("condition","").capitalize(),
        "Disponibles": product.get("available_quantity"),
        "Ventas": product.get("sold_quantity"),
        "Visitas 30d": get_item_visits(token, item_id),
        "Rating": rating,
        "Número de Reseñas": len(reviews),
        "Distribución Rating": format_rating_levels(rating_levels),
        "Nivel Vendedor": seller_rep.get("level_id","N/A"),
        "Power Seller": seller_rep.get("power_seller_status","N/A"),
        "Transacciones Totales": seller_rep.get("transactions_total","N/A"),
        "Link": product.get("permalink"),
    }

# ====
# Groq resumen opcional
# ====
def generate_summary(records):
    if not GROQ_API_KEY:
        return "Groq no está configurado."
    from groq import Groq
    client = Groq(api_key=GROQ_API_KEY)
    prompt = f"Analizá estos productos y resumí:\n{json.dumps(records, indent=2)}\nDestacá precios, ventas y oportunidades."
    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role":"user","content":prompt}],
        max_tokens=1024,
        stream=True,
    )
    text = ""
    for chunk in completion:
        if chunk.choices[0].delta.content:
            text += chunk.choices[0].delta.content
    return text

# ====
# UI
# ====
st.set_page_config("MercadoLibre Explorer", "🛒", layout="wide")
st.title("🛒 MercadoLibre Argentina Product Tracker")

# ====
# OAuth callback
# ====
params = st.query_params
if "code" in params and st.session_state["access_token"] is None:
    token = exchange_code_for_token(params["code"])
    if token:
        st.session_state["access_token"] = token
        st.query_params.clear()
        st.rerun()

# ====
# Login
# ====
if st.session_state["access_token"] is None:
    st.info("Iniciá sesión para continuar")
    st.link_button("👉 Login con MercadoLibre", get_auth_url())
    st.stop()

token = st.session_state["access_token"]

# ====
# Sidebar
# ====
st.sidebar.header("Opciones")
category = st.sidebar.selectbox("Categoría", list(CATEGORIES.keys()))
limit = st.sidebar.slider("Cantidad de productos", 5, 30, 10)

if st.sidebar.button("🔍 Buscar productos"):
    with st.spinner("Buscando productos..."):
        products = get_top_products(token, CATEGORIES[category], limit)
        st.session_state["data"] = [fetch_product_data(token, p) for p in products]

# ====
# Mostrar resultados
# ====
if st.session_state["data"]:
    df = pd.DataFrame(st.session_state["data"])
    st.subheader(f"Top {len(df)} productos en {category}")
    st.dataframe(df, use_container_width=True)

    # Gráficos
    st.plotly_chart(px.bar(df, x="Título", y="Precio", title="Precios de Productos"), use_container_width=True)
    st.plotly_chart(px.scatter(df, x="Precio", y="Ventas", hover_data=['Título'], title="Precio vs Ventas"), use_container_width=True)
    cond_counts = df["Condición"].value_counts()
    st.plotly_chart(px.pie(values=cond_counts.values, names=cond_counts.index, title="Distribución de Condición"), use_container_width=True)

    # Descargar CSV
    csv = df.to_csv(index=False)
    st.download_button("📥 Descargar CSV", csv, file_name=f"mercadolibre_{category.lower().replace(' ','_')}.csv", mime="text/csv")

    # Resumen IA
    if st.button("🧠 Generar resumen IA"):
        with st.spinner("Analizando con IA..."):
            resumen = generate_summary(df.to_dict("records"))
            st.markdown(resumen)
