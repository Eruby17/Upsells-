import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Prueba Supabase")

st.title("Prueba de conexión con Supabase")

try:
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["secret_key"]

    supabase = create_client(url, key)

    response = (
        supabase
        .table("upsell_settings")
        .select("*")
        .order("year")
        .execute()
    )

    st.success("Conexión con Supabase correcta")

    st.subheader("Configuración encontrada")
    st.dataframe(response.data, use_container_width=True)

except Exception as e:
    st.error("Error conectando con Supabase")
    st.exception(e)
