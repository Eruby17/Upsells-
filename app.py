import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARGAR CONFIGURACIÓN (LECTURA POR POSICIÓN) ---
try:
    # Leemos la pestaña Config
    df_config = conn.read(worksheet="Config", ttl=0) 
    
    # Acceso directo por posición de celda:
    # A2 es índice 0 en datos (si hay encabezado), B2 es el valor.
    # Usamos .iloc para mayor precisión técnica
    desc_actual = float(df_config.iloc[0, 1])  # Fila 2 (índice 0), Columna B (índice 1)
    tc_actual = float(df_config.iloc[1, 1])    # Fila 3 (índice 1), Columna B (índice 1)
except Exception as e:
    st.error(f"Error connecting to Google Sheets. Please check headers. {e}")
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

# --- BARRA LATERAL ---
with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.header("Admin Strategy")
    st.metric("Web Discount", f"{desc_actual}%")
    st.metric("Exchange Rate", f"${tc_actual} MXN")
    if st.button("🔄 Sync with Drive"):
        st.cache_data.clear()
        st.rerun()

# --- INTERFAZ ---
st.title("🏨 Room Upgrade Agreement")

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Guest Full Name")
    n_reserva = st.text_input("Confirmation / Folio")
    cat_orig = st.selectbox("Current Category", list(diferenciales_usd.keys()))

with col2:
    rango_fechas = st.date_input("Stay Dates", value=(datetime.now(), datetime.now() + timedelta(days=1)))
    habitacion = st.text_input("Room Number")
    cat_dest = st.selectbox("Upgrade To", list(diferenciales_usd.keys()), index=1)

# --- CÁLCULO ---
if len(rango_fechas) == 2:
    check_in, check_out = rango_fechas
    noches = (check_out - check_in).days
    
    if noches > 0:
        diff_usd_cat = diferenciales_usd[cat_dest] - diferenciales_usd[cat_orig]
        
        if diff_usd_cat > 0:
            # IMPUESTOS AL 30%
            tax_factor = 1.30 
            
            # Cálculo: (Diferencial * Descuento) * Noches * Impuestos
            factor_desc = 1 - (desc_actual / 100)
            total_usd_neto = diff_usd_cat * factor_desc * noches
            
            final_usd = total_usd_neto * tax_factor
            final_mxn = final_usd * tc_actual
            
            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("Total Upgrade USD (30% Tax Inc.)", f"${final_usd:,.2f}")
            c2.metric("Total Upgrade MXN (30% Tax Inc.)", f"${final_mxn:,.2f}")

            # --- GENERADOR DE PDF ---
            if st.button("📋 Generate Official PDF"):
                pdf = FPDF()
                pdf.add_page()
                
                # Logo
                try:
                    pdf.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", 10, 8, 45)
                except: pass
                
                pdf.ln(15)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='R')
                pdf.ln(10)
                
                # Datos Guest
                pdf.set_font("Arial", 'B', 10)
                pdf.set_fill_color(245, 245, 245)
                pdf.cell(190, 8, " GUEST INFORMATION", ln=True, fill=True)
                pdf.set_font("Arial", size=10)
                pdf.cell(95, 8, f" Name: {cliente.upper()}", border='B')
                pdf.cell(95, 8, f" Confirmation: {n_reserva}", border='B', ln=True)
                pdf.cell(95, 8, f" Dates: {check_in.strftime('%b %d')} - {check_out.strftime('%b %d, %Y')}", border='B')
                pdf.cell(95, 8, f" Nights: {noches}", border='B', ln=True)
                pdf.ln(5)
                
                # Datos Upgrade
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(190, 8, " UPGRADE DETAILS", ln=True, fill=True)
                pdf.set_font("Arial", size=10)
                pdf.cell(190, 8, f" From: {cat_orig}  >>>  To: {cat_dest}", ln=True)
                pdf.ln(5)
                
                # Financials
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(190, 10, " TOTAL ADDITIONAL CHARGES (30% TAX INCLUDED)", ln=True)
                pdf.set_font("Arial", 'B', 15)
                pdf.cell(95, 12, f" USD ${final_usd:,.2f}", border=1, align='C')
                pdf.cell(95, 12, f" MXN ${final_mxn:,.2f}", border=1, ln=True, align='C')
                
                # Legal Inglés
                pdf.ln(10)
                pdf.set_font("Arial", size=9)
                legal_text = (
                    "By signing below, I hereby authorize Casa Dorada Los Cabos Resort & Spa to apply "
                    "the aforementioned charges to my room account. I understand that this amount is "
                    "an additional fee for the room category upgrade and does not replace the original "
                    "room rate. Final charges in local currency (MXN) are subject to the hotel's "
                    "official exchange rate at the time of checkout."
                )
                pdf.multi_cell(0, 5, legal_text)
                
                # Firmas
                pdf.ln(35)
                y_sig = pdf.get_y()
                pdf.line(10, y_sig, 90, y_sig)
                pdf.line(110, y_sig, 190, y_sig)
                pdf.set_font("Arial", 'B', 9)
                pdf.set_xy(10, y_sig + 2)
                pdf.cell(80, 5, "Guest Signature", align='C')
                pdf.set_xy(110, y_sig + 2)
                pdf.cell(80, 5, "Front Desk Agent", align='C')

                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                st.download_button(f"📥 Download PDF - {cliente}", pdf_bytes, f"Upgrade_{n_reserva}.pdf", "application/pdf")
        else:
            st.error("Error: Upgrade category must be superior to the original.")
