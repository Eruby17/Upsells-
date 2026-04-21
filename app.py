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

# --- 3. CARGAR CONFIGURACIÓN (Pestaña 'Config') ---
try:
    # Intentamos leer la pestaña de configuración
    df_config = conn.read(worksheet="Config", ttl=0)
    df_config.columns = df_config.columns.str.strip().str.lower()
    df_config['parametro'] = df_config['parametro'].astype(str).str.strip().str.lower()
    
    desc_actual = float(df_config[df_config['parametro'] == 'descuento']['valor'].values[0])
    tc_actual = float(df_config[df_config['parametro'] == 'tc']['valor'].values[0])
except:
    desc_actual, tc_actual = 62.0, 17.40

# --- 4. CARGAR TARIFAS (Pestaña 'Tarifas') ---
try:
    # Leemos la pestaña. El Error 400 a veces ocurre por datos fantasma a la derecha, 
    # así que forzamos la lectura de columnas con datos.
    df_tarifas = conn.read(worksheet="Tarifas", ttl=0)
    
    if df_tarifas is not None and not df_tarifas.empty:
        # Función para limpiar "mié 01/04/2026" y dejar solo "01/04/2026"
        def extraer_fecha(texto):
            match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', str(texto))
            return match.group(1) if match else None

        df_tarifas['Fecha_Limpia'] = df_tarifas['Stay Date'].apply(extraer_fecha)
        df_tarifas = df_tarifas.dropna(subset=['Fecha_Limpia'])
        # Convertimos a fecha real de Python para comparar con el calendario
        df_tarifas['Fecha_Limpia'] = pd.to_datetime(df_tarifas['Fecha_Limpia'], dayfirst=True).dt.date
    else:
        df_tarifas = pd.DataFrame()
except Exception as e:
    st.error(f"Error procesando la pestaña Tarifas: {e}")
    df_tarifas = pd.DataFrame()

# --- 5. DIFERENCIALES DUETTO ---
diferenciales_usd = {
    "Standard Two Double Beds": 0.0,
    "Junior Suite": 75.0,
    "Deluxe Suite": 0.0,
    "Executive Suite": 150.0,
    "One Bedroom Suite Garden": 225.0,
    "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0,
    "2 Bedroom Suite": 780.0,
    "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0,
    "Penthouse 3PH": 2625.0
}

# --- 6. INTERFAZ ---
st.title("🏨 Room Upgrade Agreement")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.metric("Web Discount", f"{desc_actual}%")
    st.metric("FX Rate", f"${tc_actual} MXN")
    if st.button("🔄 Sync Drive"):
        st.cache_data.clear()
        st.rerun()

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Guest Name")
    cat_orig = st.selectbox("Original Category", list(diferenciales_usd.keys()))
    rango = st.date_input("Stay Period", value=(datetime.now().date(), (datetime.now() + timedelta(days=1)).date()))

with col2:
    n_reserva = st.text_input("Confirmation #")
    cat_dest = st.selectbox("Upgrade To", list(diferenciales_usd.keys()), index=3)
    habitacion = st.text_input("Room #")

# --- 7. LÓGICA DE CÁLCULO ---
if len(rango) == 2:
    check_in, check_out = rango
    noches = (check_out - check_in).days
    
    if noches > 0:
        # Buscamos la tarifa base del día de llegada
        tarifa_base = 0
        if not df_tarifas.empty:
            match = df_tarifas[df_tarifas['Fecha_Limpia'] == check_in]
            if not match.empty:
                tarifa_base = float(match.iloc[0]['Current Rate'])
        
        # Validación de Tarifa Cargada
        if tarifa_base == 0:
            st.error(f"❌ ERROR CRÍTICO: No se encontraron tarifas para {check_in.strftime('%B %Y')}. Por favor carga los precios en el Excel.")
        else:
            # SECUENCIA: (Tarifa Upg - Tarifa Orig) -> Descuento -> Impuestos
            total_orig_noche = tarifa_base + diferenciales_usd[cat_orig]
            total_upg_noche = tarifa_base + diferenciales_usd[cat_dest]
            
            diff_bruta = total_upg_noche - total_orig_noche
            
            if diff_bruta > 0:
                factor_desc = 1 - (desc_actual / 100)
                con_descuento = diff_bruta * factor_desc
                total_noche_usd = con_descuento * 1.30 # + 30% Taxes
                
                final_usd = total_noche_usd * noches
                final_mxn = final_usd * tc_actual
                
                st.divider()
                st.success(f"Estancia de {noches} noche(s) calculada.")
                c1, c2 = st.columns(2)
                c1.metric("Total Upgrade USD", f"${final_usd:,.2f}")
                c2.metric("Total Upgrade MXN", f"${final_mxn:,.2f}")

                # --- PDF ---
                if st.button("📝 Generate PDF"):
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                    pdf.ln(10)
                    pdf.set_font("Arial", size=11)
                    pdf.cell(0, 8, f"Guest: {cliente.upper()}", ln=True)
                    pdf.cell(0, 8, f"Confirmation: {n_reserva} | Room: {habitacion}", ln=True)
                    pdf.cell(0, 8, f"Stay: {check_in} to {check_out} ({noches} nights)", ln=True)
                    pdf.ln(5)
                    pdf.cell(0, 8, f"From: {cat_orig}  To: {cat_dest}", ln=True)
                    pdf.ln(10)
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 10, f"TOTAL DUE: USD ${final_usd:,.2f} / MXN ${final_mxn:,.2f}", ln=True)
                    
                    st.download_button("📥 Download", pdf.output(dest='S').encode('latin-1'), f"Upgrade_{n_reserva}.pdf")
            else:
                st.warning("La categoría seleccionada no es superior a la original.")
