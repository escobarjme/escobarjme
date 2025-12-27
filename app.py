import os
import streamlit as st

st.title("TEST ENV")

st.write("CLIENT_ID:", os.getenv("CLIENT_ID"))
st.write("CLIENT_SECRET:", "OK" if os.getenv("CLIENT_SECRET") else None)
st.write("REDIRECT_URI:", os.getenv("REDIRECT_URI"))
