import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- VALORES DE RESPALDO (SEGURIDAD) ---
desc_actual, tc_actual = 62.0, 17.40

# --- FUNCIÓN PARA CARGAR PESTAÑA POR NOMBRE SIMPLIFICADO ---
def cargar_pestaña(nombre):
    try:
        return conn.read(worksheet=nombre, ttl=0)
    except Exception as e:
        st.error(f"Error al leer la pestaña '{nombre}': {e}")
        return None

# --- CARGAR DATOS ---
df_1 = cargar_pestaña("1") # Config
df_2 = cargar_pestaña("2") # Tarifas

# --- PROCESAR CONFIG (PESTAÑA 1) ---
if df_1 is not None and not df_1.empty:
    try:
        df_1.columns = [str(c).strip().lower() for c in df_1.columns]
        # Buscamos 'descuento' y 'tc'
        d_row = df_1[df_1['parametro'].str.contains('descuento', case=False, na=False)]
        t_row = df_1[df_1['parametro'].str.contains('tc', case=False, na=False)]
        
        if not d_row.empty:
            desc_actual = float(str(d_row['valor'].values[0]).replace(',', '.'))
        if not t_row.empty:
            tc_actual = float(str(t_row['valor'].values[0]).replace(',', '.'))
    except:
        pass

# --- PROCESAR TARIFAS (PESTAÑA 2) ---
df_tarifas = pd.DataFrame()
if df_2 is not None and not df_2.empty:
    df_2.columns = [str(c).strip() for c in df_2.columns]
    # Normalización de fechas DD/MM/YYYY
    df_2['Fecha_Busqueda'] = pd.to_datetime(df_2['Date'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
    # Limpiar Rate
    df_2['Rate_Num'] = pd.to_numeric(df_2['Rate'].astype(str).str.replace(',', '.'), errors='coerce')
    df_tarifas = df_2.dropna(subset=['Fecha_Busqueda', 'Rate_Num'])

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
    if st.button("🔄 Refrescar"):
        st.cache_data.clear()
        st.rerun()

# --- FORMULARIO ---
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
    target = fecha_sel.strftime('%Y-%m-%d')
    match = df_tarifas[df_tarifas['Fecha_Busqueda'] == target]
    
    if not match.empty:
        tarifa_base = float(match.iloc[0]['Rate_Num'])
        
        # LÓGICA: (Upg - Orig) -> Descuento -> Impuestos
        diff_base = (tarifa_base + diferenciales[cat_dest]) - (tarifa_base + diferenciales[cat_orig])
        
        if diff_base > 0:
            total_usd = (diff_base * (1 - desc_actual/100)) * 1.30
            total_mxn = total_usd * tc_actual
            
            st.divider()
            st.metric("Total USD (Impuestos Inc.)", f"${total_usd:,.2f}")
            st.metric("Total MXN (Impuestos Inc.)", f"${total_mxn:,.2f}")
            
            if st.button("📝 Generar PDF"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                pdf.ln(10); pdf.set_font("Arial", size=12)
                pdf.cell(0, 10, f"Guest: {cliente.upper()}", ln=True)
                pdf.cell(0, 10, f"Total: USD ${total_usd:,.2f} / MXN ${total_mxn:,.2f}", ln=True)
                st.download_button("📥 Descargar", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf")
    else:
        st.warning(f"No se encontró tarifa para {fecha_sel.strftime('%d/%m/%Y')}")
