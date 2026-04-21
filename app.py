import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import re

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. CARGA DE CONFIGURACIÓN (Pestaña 'Config') ---
desc_actual, tc_actual = 62.0, 17.40 # Valores por si falla la lectura
try:
    # Intentamos leer Config. Si falla, usamos los valores de arriba.
    df_config = conn.read(worksheet="Config", ttl=0)
    if df_config is not None and not df_config.empty:
        df_config.columns = [str(c).strip().lower() for c in df_config.columns]
        # Buscamos 'descuento' y 'tc' en la columna 'parametro'
        df_config['parametro'] = df_config['parametro'].astype(str).str.strip().lower()
        
        d_val = df_config.loc[df_config['parametro'] == 'descuento', 'valor'].values[0]
        t_val = df_config.loc[df_config['parametro'] == 'tc', 'valor'].values[0]
        
        desc_actual = float(str(d_val).replace(',', '.'))
        tc_actual = float(str(t_val).replace(',', '.'))
except Exception as e:
    st.sidebar.error(f"Error en Config: {e}")

# --- 3. CARGA DE TARIFAS (Pestaña 'Tarifas') ---
df_tarifas = pd.DataFrame()
try:
    df_raw = conn.read(worksheet="Tarifas", ttl=0)
    if df_raw is not None and not df_raw.empty:
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        # Convertimos la columna Date a string puro YYYY-MM-DD para comparar sin errores
        df_raw['Fecha_Busqueda'] = pd.to_datetime(df_raw['Date'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Limpiamos la columna Rate (por si tiene comas en vez de puntos)
        df_raw['Rate_Limpio'] = df_raw['Rate'].astype(str).str.replace(',', '.').str.extract(r'(\d+\.?\d*)').astype(float)
        
        df_tarifas = df_raw.dropna(subset=['Fecha_Busqueda', 'Rate_Limpio'])
except Exception as e:
    st.error(f"Error en Tarifas: {e}")

# --- 4. DIFERENCIALES ---
diferenciales_usd = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

# --- 5. INTERFAZ ---
st.title("🏨 Upsell Agreement Generator")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.metric("Discount", f"{desc_actual}%")
    st.metric("FX Rate", f"${tc_actual} MXN")
    if st.button("🔄 Sync with Drive"):
        st.cache_data.clear()
        st.rerun()

cliente = st.text_input("Guest Full Name")
c1, c2 = st.columns(2)
with c1:
    cat_orig = st.selectbox("Original Category", list(diferenciales_usd.keys()))
    rango = st.date_input("Stay Dates", value=(datetime.now().date(), (datetime.now() + timedelta(days=1)).date()))
with c2:
    n_reserva = st.text_input("Confirmation #")
    cat_dest = st.selectbox("Upgrade To", list(diferenciales_usd.keys()), index=3)

# --- 6. CÁLCULO ---
if len(rango) == 2:
    check_in, check_out = rango
    noches = (check_out - check_in).days
    
    if noches > 0:
        # Buscamos la fecha en el formato string que creamos
        fecha_target = check_in.strftime('%Y-%m-%d')
        
        tarifa_base = 0
        if not df_tarifas.empty:
            match = df_tarifas[df_tarifas['Fecha_Busqueda'] == fecha_target]
            if not match.empty:
                tarifa_base = float(match.iloc[0]['Rate_Limpio'])

        if tarifa_base <= 0:
            st.error(f"❌ No rate found for {check_in.strftime('%d/%m/%Y')}. Revisa que la fecha esté en la columna 'Date'.")
            # Esto ayuda a debuguear:
            if not df_tarifas.empty:
                with st.expander("Ver fechas leídas del Excel"):
                    st.write(df_tarifas[['Date', 'Fecha_Busqueda', 'Rate_Limpio']].head())
        else:
            diff = (tarifa_base + diferenciales_usd[cat_dest]) - (tarifa_base + diferenciales_usd[cat_orig])
            if diff > 0:
                final_usd = (diff * (1 - desc_actual/100)) * 1.30 * noches
                final_mxn = final_usd * tc_actual
                
                st.divider()
                st.success(f"Estancia de {noches} noches.")
                st.metric("Total USD (Tax Inc.)", f"${final_usd:,.2f}")
                st.metric("Total MXN (Tax Inc.)", f"${final_mxn:,.2f}")
                
                if st.button("📝 Generate PDF"):
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                    pdf.ln(10)
                    pdf.set_font("Arial", size=12)
                    pdf.cell(0, 10, f"Guest: {cliente.upper()}", ln=True)
                    pdf.cell(0, 10, f"Total: USD ${final_usd:,.2f} / MXN ${final_mxn:,.2f}", ln=True)
                    st.download_button("📥 Download", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf")
