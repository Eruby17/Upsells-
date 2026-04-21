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

# --- 3. CARGAR CONFIGURACIÓN ---
try:
    df_config = conn.read(worksheet="Config", ttl=0)
    df_config.columns = df_config.columns.str.strip().str.lower()
    df_config['parametro'] = df_config['parametro'].astype(str).str.strip().str.lower()
    desc_actual = float(df_config[df_config['parametro'] == 'descuento']['valor'].values[0])
    tc_actual = float(df_config[df_config['parametro'] == 'tc']['valor'].values[0])
except:
    desc_actual, tc_actual = 62.0, 17.40

# --- 4. CARGAR Y LIMPIAR TARIFAS (ULTRA ROBUSTO) ---
try:
    df_tarifas = conn.read(worksheet="Tarifas", ttl=0)
    
    if df_tarifas is not None and not df_tarifas.empty:
        # Función mejorada para extraer solo DD/MM/YYYY
        def extraer_fecha_pura(texto):
            # Busca el patrón de números: 01/04/2026
            match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', str(texto))
            if match:
                return match.group(1)
            return None

        df_tarifas['Fecha_Limpia'] = df_tarifas['Stay Date'].apply(extraer_fecha_pura)
        df_tarifas = df_tarifas.dropna(subset=['Fecha_Limpia'])
        
        # Convertimos a fecha real. dayfirst=True es vital para formato DD/MM/YYYY
        df_tarifas['Fecha_Limpia'] = pd.to_datetime(df_tarifas['Fecha_Limpia'], dayfirst=True).dt.date
    else:
        st.error("La pestaña 'Tarifas' parece estar vacía.")
except Exception as e:
    st.error(f"Error técnico cargando Tarifas: {e}")

# --- 5. DIFERENCIALES ---
diferenciales_usd = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

# --- 6. INTERFAZ ---
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
    cliente = st.text_input("Guest Name")
    cat_orig = st.selectbox("Current Category", list(diferenciales_usd.keys()))
    # Calendario
    rango = st.date_input("Stay Dates", value=(datetime.now().date(), (datetime.now() + timedelta(days=1)).date()))

with col2:
    n_reserva = st.text_input("Confirmation #")
    cat_dest = st.selectbox("Upgrade Category", list(diferenciales_usd.keys()), index=3)
    habitacion = st.text_input("Room #")

# --- 7. LÓGICA DE CÁLCULO ---
if len(rango) == 2:
    check_in, check_out = rango
    noches = (check_out - check_in).days
    
    if noches > 0:
        # Búsqueda de tarifa
        tarifa_base = 0
        if not df_tarifas.empty:
            # Comparamos fecha del calendario con nuestra columna limpia
            match = df_tarifas[df_tarifas['Fecha_Limpia'] == check_in]
            if not match.empty:
                tarifa_base = float(match.iloc[0]['Current Rate'])
        
        # SI NO ENCUENTRA TARIFA
        if tarifa_base <= 0:
            st.error(f"❌ ERROR CRÍTICO: No se encontraron tarifas para el {check_in.strftime('%d/%m/%Y')}. Revisa que la fecha esté cargada en la pestaña 'Tarifas'.")
        else:
            # Lógica financiera
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
                c1.metric("Total USD (30% Tax Inc.)", f"${total_usd:,.2f}")
                c2.metric("Total MXN (30% Tax Inc.)", f"${total_mxn:,.2f}")

                # --- PDF ---
                if st.button("📝 Generate PDF"):
                    pdf = FPDF()
                    pdf.add_page()
                    # Logo
                    try: pdf.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", 10, 8, 45)
                    except: pass
                    
                    pdf.ln(20); pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                    pdf.ln(10); pdf.set_font("Arial", size=11)
                    pdf.cell(0, 8, f"Guest: {cliente.upper()}", ln=True)
                    pdf.cell(0, 8, f"Res: {n_reserva} | Room: {habitacion}", ln=True)
                    pdf.cell(0, 8, f"Dates: {check_in} to {check_out} ({noches} nights)", ln=True)
                    pdf.ln(5)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, f"TOTAL: USD ${total_usd:,.2f} / MXN ${total_mxn:,.2f}", ln=True)
                    
                    st.download_button("📥 Download Agreement", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf")
            else:
                st.warning("La categoría de upgrade debe ser superior a la original.")
