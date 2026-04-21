import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. CARGA DE CONFIGURACIÓN (Pestaña 'Config') ---
desc_actual, tc_actual = 62.0, 17.40
try:
    df_config = conn.read(worksheet="Config", ttl=0)
    if not df_config.empty:
        df_config.columns = [str(c).strip().lower() for c in df_config.columns]
        # Limpieza de valores por si vienen con coma
        d_val = str(df_config.loc[df_config['parametro'].str.contains('descuento', na=False), 'valor'].values[0])
        t_val = str(df_config.loc[df_config['parametro'].str.contains('tc', na=False), 'valor'].values[0])
        desc_actual = float(d_val.replace(',', '.'))
        tc_actual = float(t_val.replace(',', '.'))
except:
    st.sidebar.warning("Usando valores base (62% / 17.40)")

# --- 3. CARGA DE TARIFAS (Pestaña 'Tarifas') ---
df_tarifas = pd.DataFrame()
try:
    # Leemos la pestaña Tarifas
    df_raw = conn.read(worksheet="Tarifas", ttl=0)
    if not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        # TRUCO MAESTRO: Convertimos cualquier formato de fecha a 'AAAA-MM-DD'
        # Esto soluciona el error de "No rate found"
        df_raw['Fecha_ID'] = pd.to_datetime(df_raw['Date'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Limpiamos el Rate
        df_raw['Rate_Num'] = pd.to_numeric(df_raw['Rate'].astype(str).str.replace(',', '.'), errors='coerce')
        
        df_tarifas = df_raw.dropna(subset=['Fecha_ID', 'Rate_Num'])
except Exception as e:
    st.error(f"Error cargando la pestaña Tarifas: {e}")

# --- 4. DIFERENCIALES ---
diferenciales = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

# --- 5. INTERFAZ ---
st.title("🏨 Upsell Agreement Generator")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.metric("Descuento", f"{desc_actual}%")
    st.metric("T.C.", f"${tc_actual} MXN")
    if st.button("🔄 Sincronizar Datos"):
        st.cache_data.clear()
        st.rerun()

# --- FORMULARIO ---
cliente = st.text_input("Nombre del Huésped")
col1, col2 = st.columns(2)
with col1:
    cat_orig = st.selectbox("Categoría Original", list(diferenciales.keys()))
    fecha_sel = st.date_input("Fecha de Estancia", datetime.now())
with col2:
    n_reserva = st.text_input("Confirmación #")
    cat_dest = st.selectbox("Upgrade a", list(diferenciales.keys()), index=3)

# --- 6. CÁLCULO ---
fecha_buscar = fecha_sel.strftime('%Y-%m-%d')
tarifa_base = 0

if not df_tarifas.empty:
    match = df_tarifas[df_tarifas['Fecha_ID'] == fecha_buscar]
    if not match.empty:
        tarifa_base = float(match.iloc[0]['Rate_Num'])
    else:
        st.error(f"❌ No se encontró tarifa para {fecha_sel.strftime('%d/%m/%Y')}")
        # DEBUG: Mostrar qué fechas sí hay en el Excel si falla
        with st.expander("Ver fechas disponibles en el Excel"):
            st.write(df_tarifas[['Date', 'Fecha_ID', 'Rate_Num']].head(10))

if tarifa_base > 0:
    # Lógica: (Upg - Orig) -> Descuento -> Impuestos
    diff_base = (tarifa_base + diferenciales[cat_dest]) - (tarifa_base + diferenciales[cat_orig])
    
    if diff_base > 0:
        total_usd = (diff_base * (1 - desc_actual/100)) * 1.30
        total_mxn = total_usd * tc_actual
        
        st.divider()
        st.success("Cálculo realizado con éxito")
        st.metric("Total USD (Impuestos Inc.)", f"${total_usd:,.2f}")
        st.metric("Total MXN (Impuestos Inc.)", f"${total_mxn:,.2f}")
        
        if st.button("📝 Generar PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
            pdf.ln(10)
            pdf.set_font("Arial", size=12)
            pdf.cell(0, 10, f"Guest: {cliente.upper()}", ln=True)
            pdf.cell(0, 10, f"Date: {fecha_sel.strftime('%d/%m/%Y')}", ln=True)
            pdf.cell(0, 10, f"Total: USD ${total_usd:,.2f} / MXN ${total_mxn:,.2f}", ln=True)
            st.download_button("📥 Descargar", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf")
