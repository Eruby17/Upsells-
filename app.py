import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARGAR CONFIGURACIÓN (DESDE LA SEGUNDA HOJA) ---
try:
    # Intentamos leer explícitamente la pestaña 'Config'
    df_config = conn.read(worksheet="Config", ttl=0)
    
    if df_config is not None and not df_config.empty:
        # Limpiamos nombres de columnas y datos para evitar errores de mayúsculas/espacios
        df_config.columns = df_config.columns.str.strip().str.lower()
        df_config['parametro'] = df_config['parametro'].astype(str).str.strip().str.lower()
        
        # Extraemos valores usando filtros (más seguro que por posición)
        desc_actual = float(df_config[df_config['parametro'] == 'descuento']['valor'].values[0])
        tc_actual = float(df_config[df_config['parametro'] == 'tc']['valor'].values[0])
    else:
        st.warning("⚠️ 'Config' sheet found but it's empty.")
        desc_actual, tc_actual = 55.0, 18.0
except Exception as e:
    # Si falla por nombre, intentamos leer la configuración por defecto
    st.error(f"❌ Error al conectar con la pestaña 'Config': {e}")
    st.info("Asegúrate de que la segunda pestaña se llame exactamente 'Config' y tenga los encabezados 'parametro' y 'valor'.")
    desc_actual, tc_actual = 55.0, 18.0

# --- DIFERENCIALES DUETTO (USD) ---
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

# --- SIDEBAR ---
with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.header("Revenue Strategy")
    st.metric("Discount Applied", f"{desc_actual}%")
    st.metric("T.C. (FX Rate)", f"${tc_actual} MXN")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# --- INTERFAZ PRINCIPAL ---
st.title("🏨 Room Upgrade Agreement")

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Guest Name")
    n_reserva = st.text_input("Confirmation #")
    cat_orig = st.selectbox("Current Category", list(diferenciales_usd.keys()))

with col2:
    rango_fechas = st.date_input("Stay Dates", value=(datetime.now(), datetime.now() + timedelta(days=1)))
    habitacion = st.text_input("Room #")
    cat_dest = st.selectbox("Upgrade Category", list(diferenciales_usd.keys()), index=1)

# --- LÓGICA DE CÁLCULO ---
if len(rango_fechas) == 2:
    check_in, check_out = rango_fechas
    noches = (check_out - check_in).days
    
    if noches > 0:
        diff_usd_base = diferenciales_usd[cat_dest] - diferenciales_usd[cat_orig]
        
        if diff_usd_base > 0:
            # IMPUESTOS AL 30%
            tax_factor = 1.30 
            factor_desc = 1 - (desc_actual / 100)
            
            # Cálculo final
            total_usd_final = (diff_usd_base * factor_desc * noches) * tax_factor
            total_mxn_final = total_usd_final * tc_actual
            
            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("Total USD (30% Tax Inc.)", f"${total_usd_final:,.2f}")
            c2.metric("Total MXN (30% Tax Inc.)", f"${total_mxn_final:,.2f}")

            # --- GENERADOR DE PDF ---
            if st.button("📝 Generate PDF Agreement"):
                pdf = FPDF()
                pdf.add_page()
                try:
                    pdf.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", 10, 8, 45)
                except: pass
                
                pdf.ln(15)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='R')
                pdf.ln(10)
                
                pdf.set_font("Arial", 'B', 10)
                pdf.set_fill_color(245, 245, 245)
                pdf.cell(190, 8, " GUEST DETAILS", ln=True, fill=True)
                pdf.set_font("Arial", size=10)
                pdf.cell(95, 8, f" Name: {cliente.upper()}", border='B')
                pdf.cell(95, 8, f" Confirmation: {n_reserva}", border='B', ln=True)
                pdf.cell(95, 8, f" Stay: {check_in.strftime('%b %d')} - {check_out.strftime('%b %d, %Y')}", border='B')
                pdf.cell(95, 8, f" Nights: {noches} | Room: {habitacion}", border='B', ln=True)
                pdf.ln(10)
                
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(190, 10, " TOTAL ADDITIONAL CHARGES (30% TAX INCLUDED)", ln=True)
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(95, 12, f" USD ${total_usd_final:,.2f}", border=1, align='C')
                pdf.cell(95, 12, f" MXN ${total_mxn_final:,.2f}", border=1, ln=True, align='C')
                
                pdf.ln(10)
                pdf.set_font("Arial", size=9)
                pdf.multi_cell(0, 5, "By signing below, I hereby authorize Casa Dorada Los Cabos to post these charges to my room account. Final charges in MXN are subject to the hotel's exchange rate at checkout.")
                
                pdf.ln(30)
                y_sig = pdf.get_y()
                pdf.line(10, y_sig, 90, y_sig)
                pdf.line(110, y_sig, 190, y_sig)
                pdf.set_font("Arial", 'B', 9)
                pdf.set_xy(10, y_sig + 2)
                pdf.cell(80, 5, "Guest Signature", align='C')
                pdf.set_xy(110, y_sig + 2)
                pdf.cell(80, 5, "Front Desk Agent", align='C')

                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                st.download_button(f"📥 Download PDF", pdf_bytes, f"Upgrade_{n_reserva}.pdf", "application/pdf")
        else:
            st.error("Upgrade category must be superior to the original.")
