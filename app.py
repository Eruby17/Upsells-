import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARGA DE CONFIGURACIÓN ---
desc_actual, tc_actual = 62.0, 17.40
try:
    df_config = conn.read(worksheet="Config", ttl=0)
    if df_config is not None:
        df_config.columns = [str(c).strip().lower() for c in df_config.columns]
        d_val = str(df_config.loc[df_config['parametro'].str.contains('descuento', na=False), 'valor'].values[0])
        t_val = str(df_config.loc[df_config['parametro'].str.contains('tc', na=False), 'valor'].values[0])
        desc_actual = float(d_val.replace(',', '.'))
        tc_actual = float(t_val.replace(',', '.'))
except: pass

# --- CARGA DE TARIFAS (CON MANEJO DE ERROR 400) ---
df_tarifas = pd.DataFrame()
try:
    # Leemos la pestaña especificando el nombre exacto
    df_raw = conn.read(worksheet="Tarifas", ttl=0)
    
    if df_raw is not None and not df_raw.empty:
        # Limpiar nombres de columnas por si tienen espacios
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        # Convertir Date a string estandarizado YYYY-MM-DD
        df_raw['Fecha_Busqueda'] = pd.to_datetime(df_raw['Date'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
        # Limpiar Rate de cualquier símbolo o coma
        df_raw['Rate_Num'] = pd.to_numeric(df_raw['Rate'].astype(str).str.replace(',', '.'), errors='coerce')
        
        df_tarifas = df_raw.dropna(subset=['Fecha_Busqueda', 'Rate_Num'])
except Exception as e:
    st.error(f"Error de Conexión (Bad Request): Revisa que la pestaña se llame 'Tarifas' y que no haya columnas vacías a la derecha.")
    st.info("Sugerencia: En Google Sheets, ve a 'Archivo' > 'Compartir' y asegúrate de que 'Cualquier persona con el enlace' sea 'Lector'.")

# --- DIFERENCIALES ---
diferenciales = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

# --- INTERFAZ ---
st.title("🏨 Upsell Agreement Generator")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.metric("Descuento", f"{desc_actual}%")
    st.metric("T.C.", f"${tc_actual} MXN")
    if st.button("🔄 Refrescar Datos"):
        st.cache_data.clear()
        st.rerun()

cliente = st.text_input("Nombre del Huésped")
c1, c2 = st.columns(2)
with c1:
    cat_orig = st.selectbox("Categoría Original", list(diferenciales.keys()))
    fecha_sel = st.date_input("Fecha de Estancia", datetime.now().date())
with c2:
    n_reserva = st.text_input("Confirmación #")
    cat_dest = st.selectbox("Upgrade a", list(diferenciales.keys()), index=3)

# --- CÁLCULO ---
if not df_tarifas.empty:
    fecha_target = fecha_sel.strftime('%Y-%m-%d')
    match = df_tarifas[df_tarifas['Fecha_Busqueda'] == fecha_target]
    
    if not match.empty:
        tarifa_base = float(match.iloc[0]['Rate_Num'])
        
        # Lógica: (Upg - Orig) -> Descuento -> Impuestos
        diff_base = (tarifa_base + diferenciales[cat_dest]) - (tarifa_base + diferenciales[cat_orig])
        
        if diff_base > 0:
            total_usd = (diff_base * (1 - desc_actual/100)) * 1.30
            total_mxn = total_usd * tc_actual
            
            st.divider()
            st.metric("Total USD (Tax Inc.)", f"${total_usd:,.2f}")
            st.metric("Total MXN (Tax Inc.)", f"${total_mxn:,.2f}")
            
            if st.button("📝 Generar PDF"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                pdf.ln(10)
                pdf.set_font("Arial", size=12)
                pdf.cell(0, 10, f"Guest: {cliente.upper()}", ln=True)
                pdf.cell(0, 10, f"Total: USD ${total_usd:,.2f} / MXN ${total_mxn:,.2f}", ln=True)
                st.download_button("📥 Descargar", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf")
    else:
        st.warning(f"No se encontró tarifa para la fecha {fecha_sel.strftime('%d/%m/%Y')}")
