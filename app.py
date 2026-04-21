import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import re

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- 2. CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. INICIALIZACIÓN DE VARIABLES (Evita NameError) ---
df_tarifas = pd.DataFrame()
desc_actual = 62.0
tc_actual = 17.40

# --- 4. CARGAR CONFIGURACIÓN ---
try:
    df_config = conn.read(worksheet="Config", ttl=0)
    if df_config is not None and not df_config.empty:
        df_config.columns = df_config.columns.str.strip().str.lower()
        df_config['parametro'] = df_config['parametro'].astype(str).str.strip().str.lower()
        desc_actual = float(df_config[df_config['parametro'] == 'descuento']['valor'].values[0])
        tc_actual = float(df_config[df_config['parametro'] == 'tc']['valor'].values[0])
except Exception as e:
    st.sidebar.warning(f"Usando valores de respaldo (Config): {e}")

# --- 5. CARGAR TARIFAS (ULTRA ROBUSTO) ---
try:
    df_raw = conn.read(worksheet="Tarifas", ttl=0)
    
    if df_raw is not None and not df_raw.empty:
        # Función para extraer solo DD/MM/YYYY
        def extraer_fecha(texto):
            match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', str(texto))
            return match.group(1) if match else None

        df_raw['Fecha_Limpia'] = df_raw['Stay Date'].apply(extraer_fecha)
        df_raw = df_raw.dropna(subset=['Fecha_Limpia'])
        df_raw['Fecha_Limpia'] = pd.to_datetime(df_raw['Fecha_Limpia'], dayfirst=True).dt.date
        df_tarifas = df_raw # Asignamos a la variable global
    else:
        st.error("La pestaña 'Tarifas' está vacía.")
except Exception as e:
    st.error(f"Error cargando tarifario: {e}")

# --- 6. DIFERENCIALES ---
diferenciales_usd = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

# --- 7. INTERFAZ ---
st.title("🏨 Room Upgrade Agreement")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.metric("Discount", f"{desc_actual}%")
    st.metric("FX Rate", f"${tc_actual} MXN")
    if st.button("🔄 Sync Drive"):
        st.cache_data.clear()
        st.rerun()

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Guest Full Name")
    cat_orig = st.selectbox("Current Category", list(diferenciales_usd.keys()))
    rango = st.date_input("Stay Dates", value=(datetime.now().date(), (datetime.now() + timedelta(days=1)).date()))

with col2:
    n_reserva = st.text_input("Confirmation #")
    cat_dest = st.selectbox("Upgrade Category", list(diferenciales_usd.keys()), index=3)
    habitacion = st.text_input("Room #")

# --- 8. LÓGICA DE CÁLCULO ---
if len(rango) == 2:
    check_in, check_out = rango
    noches = (check_out - check_in).days
    
    if noches > 0:
        tarifa_base = 0
        
        # Validación de búsqueda
        if not df_tarifas.empty:
            match = df_tarifas[df_tarifas['Fecha_Limpia'] == check_in]
            if not match.empty:
                tarifa_base = float(match.iloc[0]['Current Rate'])
        
        if tarifa_base <= 0:
            st.error(f"❌ ERROR: No se encontró tarifa para el {check_in.strftime('%d/%m/%Y')}.")
        else:
            # Cálculo financiero
            orig_total = tarifa_base + diferenciales_usd[cat_orig]
            upg_total = tarifa_base + diferenciales_usd[cat_dest]
            diff_bruta = upg_total - orig_total
            
            if diff_bruta > 0:
                final_noche_usd = (diff_bruta * (1 - desc_actual/100)) * 1.30
                total_usd = final_noche_usd * noches
                total_mxn = total_usd * tc_actual

                st.divider()
                st.success(f"Cálculo listo para {noches} noche(s).")
                c1, c2 = st.columns(2)
                c1.metric("Total USD", f"${total_usd:,.2f}")
                c2.metric("Total MXN", f"${total_mxn:,.2f}")

                # --- 9. GENERACIÓN PDF ---
                if st.button("📝 Generate PDF"):
                    pdf = FPDF()
                    pdf.add_page()
                    try: pdf.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", 10, 8, 45)
                    except: pass
                    
                    pdf.ln(20); pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                    pdf.ln(10); pdf.set_font("Arial", size=11)
                    pdf.cell(0, 8, f"Guest: {cliente.upper()}", ln=True)
                    pdf.cell(0, 8, f"Confirmation: {n_reserva} | Room: {habitacion}", ln=True)
                    pdf.cell(0, 8, f"Stay: {check_in} to {check_out} ({noches} nights)", ln=True)
                    pdf.ln(5)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, f"TOTAL TO PAY: USD ${total_usd:,.2f} / MXN ${total_mxn:,.2f}", ln=True)
                    
                    st.download_button("📥 Download PDF", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf")
            else:
                st.warning("La categoría de upgrade debe ser superior.")
