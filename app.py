import os
import time
import requests
import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

# ===============================
# ENV CONFIG (Railway)
# ===============================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

if not all([CLIENT_ID, CLIENT_SECRET, REDIRECT_URI]):
    raise RuntimeError("Faltan variables de entorno OAuth (CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)")

AUTH_URL = "https://auth.mercadolibre.com.ar/authorization"
TOKEN_URL = "https://api.mercadolibre.com/oauth/token"
SITE_ID = "MLA"

CATEGORIES = {
    "Electronics": "MLA1000",
    "Computers": "MLA1648",
    "Cellphones": "MLA1051",
    "Home & Garden": "MLA1574",
    "Sports": "MLA1276"
}

# ===============================
# OAUTH HELPERS
# ===============================
def get_auth_url():
    return (
        f"{AUTH_URL}"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )

def exchange_code_for_token(code):
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=10)
    r.raise_for_status()
    data = r.json()
    data["expires_at"] = time.time() + data["expires_in"]
    return data

def refresh_access_token(refresh_token):
    payload = {
        "grant_type": "refresh_token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token
    }
    r = requests.post(TOKEN_URL, data=payload, timeout=10)
    r.raise_for_status()
    data = r.json()
    data["expires_at"] = time.time() + data["expires_in"]
    return data

def get_valid_token():
    token = st.session_state.token
    if time.time() > token["expires_at"]:
        token = refresh_access_token(token["refresh_token"])
        st.session_state.token = token
    return token["access_token"]

# ===============================
# MERCADOLIBRE API
# ===============================
def get_top_products(access_token, category_id, limit):
    url = f"https://api.mercadolibre.com/sites/{SITE_ID}/search"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "category": category_id,
        "sort": "sold_quantity_desc",
        "limit": limit
    }
    r = requests.get(url, headers=headers, params=params, timeout=10)
    r.raise_for_status()
    return r.json()["results"]

def get_item_visits(access_token, item_id):
    url = f"https://api.mercadolibre.com/items/{item_id}/visits/time_window"
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "last": 30,
        "unit": "day",
        "ending": datetime.now().strftime("%Y-%m-%d")
    }
    r = requests.get(url, headers=headers, params=params, timeout=10)
    if r.status_code != 200:
        return "N/A"
    return r.json().get("total_visits", "N/A")

def get_item_rating(access_token, item_id):
    url = f"https://api.mercadolibre.com/reviews/item/{item_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return "N/A", 0
    data = r.json()
    return data.get("rating_average", "N/A"), len(data.get("reviews", []))

def get_seller_reputation(access_token, seller_id):
    url = f"https://api.mercadolibre.com/users/{seller_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(url, headers=headers, timeout=10)
    if r.status_code != 200:
        return {}
    rep = r.json().get("seller_reputation", {})
    return {
        "level": rep.get("level_id", "N/A"),
        "power_seller": rep.get("power_seller_status", "N/A")
    }

def fetch_product(access_token, product):
    visits = get_item_visits(access_token, product["id"])
    rating, reviews = get_item_rating(access_token, product["id"])
    seller = get_seller_reputation(access_token, product["seller"]["id"])

    return {
        "Title": product["title"],
        "Price": product["price"],
        "Condition": product["condition"],
        "Available": product["available_quantity"],
        "Visits (30d)": visits,
        "Rating": rating,
        "Reviews": reviews,
        "Seller Level": seller.get("level"),
        "Power Seller": seller.get("power_seller"),
        "Link": product["permalink"]
    }

# ===============================
# STREAMLIT APP
# ===============================
def main():
    st.set_page_config("MercadoLibre Scanner", "🛒", layout="wide")
    st.title("🛒 MercadoLibre Product Scanner (Argentina)")

    # OAuth flow
    query_params = st.experimental_get_query_params()

    if "token" not in st.session_state:
        if "code" not in query_params:
            st.warning("Necesitás iniciar sesión con MercadoLibre")
            st.markdown(f"[🔐 Login con MercadoLibre]({get_auth_url()})")
            st.stop()
        else:
            token = exchange_code_for_token(query_params["code"][0])
            st.session_state.token = token
            st.experimental_set_query_params()

    access_token = get_valid_token()

    # Sidebar
    st.sidebar.header("Filtros")
    category = st.sidebar.selectbox("Categoría", list(CATEGORIES.keys()))
    limit = st.sidebar.slider("Cantidad de productos", 5, 50, 20)

    if st.sidebar.button("🔎 Escanear productos"):
        with st.spinner("Escaneando MercadoLibre..."):
            products = get_top_products(access_token, CATEGORIES[category], limit)
            data = [fetch_product(access_token, p) for p in products]
            st.session_state.data = data

    if "data" in st.session_state:
        df = pd.DataFrame(st.session_state.data)
        st.subheader(f"Top productos – {category}")
        st.dataframe(
            df,
            column_config={"Link": st.column_config.LinkColumn("Link")},
            hide_index=True
        )

        fig = px.bar(df, x="Title", y="Price", title="Precios de productos")
        st.plotly_chart(fig, use_container_width=True)

        csv = df.to_csv(index=False)
        st.download_button("⬇ Descargar CSV", csv, "productos_ml.csv", "text/csv")

if __name__ == "__main__":
    main()

