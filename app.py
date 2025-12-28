import os
import requests
import streamlit as st
import pandas as pd

# ... (Configuración de variables de entorno y OAuth igual que antes)

@st.cache_data(ttl=300)
def get_any_data(token, category_id, limit=20):
    headers = {"Authorization": f"Bearer {token}"}
    
    # ESTRATEGIA 1: Intentar Highlights (Ranking oficial)
    url_h = f"{API_BASE}/highlights/{SITE_ID}/category/{category_id}"
    r_h = requests.get(url_h, headers=headers, timeout=10)
    
    if r_h.status_code == 200 and r_h.json().get("content"):
        return r_h.json().get("content")[:limit]

    # ESTRATEGIA 2: Fallback a Search (Búsqueda por ventas)
    # Usamos sort=sold_quantity_desc para simular el ranking
    st.info("💡 Ranking oficial no disponible. Generando ranking mediante volumen de ventas...")
    url_s = f"{API_BASE}/sites/{SITE_ID}/search?category={category_id}&sort=sold_quantity_desc&limit={limit}"
    r_s = requests.get(url_s, headers=headers, timeout=10)
    
    if r_s.status_code == 200:
        results = r_s.json().get("results", [])
        # Normalizamos el formato para que sea compatible con el resto del script
        return [{"id": x["id"], "type": "ITEM"} for x in results]
    
    return []

def get_item_details(token, item_id):
    headers = {"Authorization": f"Bearer {token}"}
    # Consultamos el item directamente
    r = requests.get(f"{API_BASE}/items/{item_id}", headers=headers, timeout=10)
    if r.status_code == 200:
        data = r.json()
        return {
            "title": data.get("title"),
            "price": data.get("price"),
            # Si sold_quantity es privado, intentamos traer 'order_backend' o un valor estimado
            "sold_quantity": data.get("sold_quantity", "Privado"),
            "permalink": data.get("permalink")
        }
    return None

# =====================
# LÓGICA DE BÚSQUEDA (Actualizada)
# =====================
if buscar:
    with st.spinner("Conectando con la API de Mercado Libre..."):
        raw_items = get_any_data(token, CATEGORIES[cat_name], limit)
        
        if not raw_items:
            st.error(f"No se obtuvieron resultados para {cat_name}. Verifica que el ID de categoría sea correcto.")
        else:
            final_results = []
            progress = st.progress(0)
            
            for i, raw in enumerate(raw_items):
                detail = get_item_details(token, raw["id"])
                if detail:
                    final_results.append({
                        "Posición": i + 1,
                        "Título": detail["title"],
                        "Precio": detail["price"],
                        "Vendidos": detail["sold_quantity"],
                        "Link": detail["permalink"]
                    })
                progress.progress((i + 1) / len(raw_items))
            
            st.session_state.data = final_results
            st.rerun()
