mport os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px

# =====================
# Variables de entorno (Railway)
# =====================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")
SITE_ID = os.getenv("SITE_ID", "MLA")

# Debug visual
st.write("SITE_ID:", SITE_ID)

if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
    st.error("❌ Variables de entorno faltantes en Railway")
    st.stop()
