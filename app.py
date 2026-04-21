import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- 2. CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. VARIABLES POR DEFECTO ---
df_tarifas = pd.DataFrame()
desc_actual = 62.0
tc_actual = 17.40

# --- 4. CARGAR CONFIGURACIÓN ---
try:
    df_config = conn.read(worksheet="Config", ttl=0)
    if df_config is not None and not df_config.empty:
        df_config.columns = [str(c).strip().lower() for c in df_config.columns]
        df_config['parametro'] = df_config['parametro'].astype(str).str.strip().lower()
        desc_actual = float(df_config[df_config['parametro'] == 'descuento']['valor'].values[0])
        tc_actual = float(df_config[df_config['parametro'] == 'tc']['valor'].values[0])
except:
    pass

# --- 5. CARGAR TARIFAS (NORMALIZACIÓN TOTAL) ---
try:
    df_raw = conn.read(worksheet="Tarifas", ttl=0)
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        # Convertimos la columna 'Date' a fecha y luego a STRING formato YYYY-MM-DD
        # Esto elimina cualquier error de zona horaria o formato de texto
        df_raw['Fecha_ID'] = pd.to_datetime(df_raw['Date'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
        df_tarifas = df_raw.dropna(subset=['Fecha_ID', 'Rate']).copy()
        df_tarifas['Rate'] = pd.to_numeric(df_tarifas['Rate'], errors='coerce')
except Exception as e:
    st.error(f"Error vinculando el tarifario: {e}")

# --- 6. DIFERENCIALES ---
diferenciales_usd = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

# --- 7. INTERFAZ ---
st.title("🏨 Upsell Agreement Generator")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.metric("Web Discount", f"{desc_actual}%")
    st.metric("FX Rate", f"${tc_actual} MXN")
    if st.button("🔄 Sync with Drive"):
        st.cache_data.clear()
        st.rerun()

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Guest Full Name")
    cat_orig = st.selectbox("Original Category", list(diferenciales_usd.keys()))
    rango = st.date_input("Stay Period", value=(datetime.now().date(), (datetime.now() + timedelta(days=1)).date()))

with col2:
    n_reserva = st.text_input("Confirmation #")
    cat_dest = st.selectbox("Upgrade To", list(diferenciales_usd.keys()), index=3)
    habitacion = st.text_input("Room #")

# --- 8. LÓGICA DE CÁLCULO ---
if len(rango) == 2:
    arrival, departure = rango
    noches = (departure - arrival).days
    
    if noches > 0:
        # Convertimos la fecha del calendario al MISMO formato string que el Excel
        fecha_busqueda = arrival.strftime('%Y-%m-%d')
        
        tarifa_base = 0
        if not df_tarifas.empty:
            match = df_tarifas[df_tarifas['Fecha_ID'] == fecha_busqueda]
            if not match.empty:
                tarifa_base = float(match.iloc[0]['Rate'])
        
        if tarifa_base <= 0:
            st.error(f"❌ CRITICAL ERROR: No rate found for {arrival.strftime('%d/%m/%Y')}. Check 'Date' column in Excel.")
            # Debug para el administrador (puedes borrarlo luego)
            if not df_tarifas.empty:
                st.write("Fechas disponibles en Excel:", df_tarifas['Fecha_ID'].unique()[:3])
        else:
            orig_total = tarifa_base + diferenciales_usd[cat_orig]
            upg_total = tarifa_base + diferenciales_usd[cat_dest]
            gap = upg_total - orig_total
            
            if gap > 0:
                final_night_usd = (gap * (1 - desc_actual/100)) * 1.30
                total_usd = final_night_usd * noches
                total_mxn = total_usd * tc_actual

                st.divider()
                st.success(f"Stay of {noches} night(s) calculated.")
                c1, c2 = st.columns(2)
                c1.metric("Total USD (Inc. Tax)", f"${total_usd:,.2f}")
                c2.metric("Total MXN (Inc. Tax)", f"${total_mxn:,.2f}")

                if st.button("📝 Generate Official PDF"):
                    pdf = FPDF()
                    pdf.add_page()
                    try: pdf.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", 10, 8, 45)
                    except: pass
                    pdf.ln(20); pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                    pdf.ln(10); pdf.set_font("Arial", size=10)
                    pdf.cell(0, 8, f"Guest: {cliente.upper()}", ln=True)
                    pdf.cell(0, 8, f"Arrival: {arrival.strftime('%d/%m/%Y')} | Departure: {departure.strftime('%d/%m/%Y')}", ln=True)
                    pdf.cell(0, 8, f"Total Nights: {noches} | Room: {habitacion}", ln=True)
                    pdf.ln(5); pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, f"TOTAL: USD ${total_usd:,.2f} / MXN ${total_mxn:,.2f}", ln=True)
                    st.download_button("📥 Download PDF", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf")
            else:
                st.warning("Selected category is not an upgrade.")
