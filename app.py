import streamlit as st
import requests

# ========== CONFIGURACIÓN ==========
CLIENT_ID = "575488757105811"
CLIENT_SECRET = "8Vut2kVEr40hqZDrRamZu5NwfShkur9z"
REDIRECT_URI = "http://localhost:8501"  # Cambia por la URL que te dé ngrok

# ========== INTERFAZ ==========
st.set_page_config(page_title="Mercado Libre API - Debug", layout="centered")
st.title("🔍 Debug Mercado Libre OAuth")

# Redirección al login de Mercado Libre
def redirect_to_login():
    auth_url = (
        f"https://auth.mercadolibre.com.ar/authorization"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    st.markdown(f"[👉 Iniciar sesión en Mercado Libre]({auth_url})", unsafe_allow_html=True)

# Intercambio del 'code' por el token de acceso
def exchange_code_for_token(code: str) -> str:
    st.write("📡 Enviando request para obtener token...")
    token_url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    st.json(payload)  # Log del payload enviado
    response = requests.post(token_url, data=payload)
    st.write(f"🔍 Status code: {response.status_code}")
    st.write("Respuesta completa del servidor:")
    st.json(response.json())
    response.raise_for_status()
    return response.json()["access_token"]

# ========== FLUJO DE AUTENTICACIÓN ==========
query_params = st.query_params
st.write("📌 Query params actuales:", query_params)

if "access_token" not in st.session_state:
    if "code" not in query_params:
        st.info("🔐 No hay código en la URL, debes iniciar sesión primero")
        redirect_to_login()
        st.stop()
    else:
        code = query_params["code"]
        st.success(f"✅ Código recibido: {code}")
        try:
            access_token = exchange_code_for_token(code)
            st.session_state["access_token"] = access_token
            st.success("✅ ¡Autenticación exitosa!")
        except Exception as e:
            st.error(f"❌ Error al obtener token: {e}")
            st.stop()

# ========== CONSULTAS ==========
access_token = st.session_state.get("access_token")
if access_token:
    st.write("🔑 Token actual:")
    st.code(access_token)

    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        st.write("📡 Solicitando información del usuario...")
        user_info = requests.get("https://api.mercadolibre.com/users/me", headers=headers).json()
        st.subheader("👤 Información de tu cuenta Mercado Libre")
        st.json(user_info)
    except Exception as e:
        st.error(f"Error al acceder a la API: {e}")

