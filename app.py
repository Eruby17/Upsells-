import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARGAR CONFIGURACIÓN (CONEXIÓN ROBUSTA) ---
try:
    # Leemos la pestaña 'Config'. ttl=0 para forzar datos frescos del Drive.
    # header=0 indica que la primera fila son los títulos (parametro, valor)
    df_config = conn.read(worksheet="Config", ttl=0, header=0) 
    
    if df_config is not None and not df_config.empty:
        # Acceso por posición: 
        # Fila 0 de datos (A2/B2 en Excel), Columna 1 (B en Excel)
        desc_actual = float(df_config.iloc[0, 1]) 
        # Fila 1 de datos (A3/B3 en Excel), Columna 1 (B en Excel)
        tc_actual = float(df_config.iloc[1, 1])
    else:
        st.error("Sheet 'Config' is empty or headers are missing.")
        desc_actual, tc_actual = 55.0, 18.0
except Exception as e:
    st.warning(f"⚠️ Error connecting to Drive: {e}. Using default values.")
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

# --- BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.header("Admin Strategy")
    st.metric("Discount Applied", f"{desc_actual}%")
    st.metric("T.C. / FX Rate", f"${tc_actual} MXN")
    st.divider()
    if st.button("🔄 Sync with Google Drive"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Revenue: Changes in the Excel file are reflected after syncing.")

# --- INTERFAZ PRINCIPAL ---
st.title("🏨 Room Upgrade Agreement")

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Guest Full Name")
    n_reserva = st.text_input("Confirmation / Folio Number")
    cat_orig = st.selectbox("Current Category (Reserved)", list(diferenciales_usd.keys()))

with col2:
    rango_fechas = st.date_input("Stay Period", value=(datetime.now(), datetime.now() + timedelta(days=1)))
    habitacion = st.text_input("Assigned Room Number")
    cat_dest = st.selectbox("Upgrade To", list(diferenciales_usd.keys()), index=1)

# --- CÁLCULO DE UPSELL ---
if len(rango_fechas) == 2:
    check_in, check_out = rango_fechas
    noches = (check_out - check_in).days
    
    if noches > 0:
        # 1. Diferencia entre categorías (USD)
        diff_base_usd = diferenciales_usd[cat_dest] - diferenciales_usd[cat_orig]
        
        if diff_base_usd > 0:
            # 2. Aplicar estrategia de descuento (ej. 55%)
            factor_desc = 1 - (desc_actual / 100)
            precio_noche_neto_usd = diff_base_usd * factor_desc
            
            # 3. Aplicar Impuestos del 30% (Factor 1.30)
            tax_factor = 1.30
            total_usd_final = (precio_noche_neto_usd * noches) * tax_factor
            total_mxn_final = total_usd_final * tc_actual
            
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.metric("Total Upgrade USD (30% Tax Inc.)", f"${total_usd_final:,.2f}")
            with c2:
                st.metric("Total Upgrade MXN (30% Tax Inc.)", f"${total_mxn_final:,.2f}")

            # --- GENERADOR DE PDF ---
            if st.button("📋 Generate Official Agreement"):
                pdf = FPDF()
                pdf.add_page()
                
                # Logo Corporativo
                try:
                    pdf.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", 10, 8, 45)
                except: pass
                
                pdf.ln(15)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='R')
                pdf.ln(10)
                
                # Sección Guest Info
                pdf.set_font("Arial", 'B', 10)
                pdf.set_fill_color(245, 245, 245)
                pdf.cell(190, 8, " GUEST & RESERVATION DETAILS", ln=True, fill=True)
                pdf.set_font("Arial", size=10)
                pdf.cell(95, 8, f" Name: {cliente.upper()}", border='B')
                pdf.cell(95, 8, f" Confirmation: {n_reserva}", border='B', ln=True)
                pdf.cell(95, 8, f" Dates: {check_in.strftime('%b %d')} - {check_out.strftime('%b %d, %Y')}", border='B')
                pdf.cell(95, 8, f" Nights: {noches} | Room: {habitacion}", border='B', ln=True)
                pdf.ln(5)
                
                # Detalles del Cambio
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(190, 8, " UPGRADE DETAILS", ln=True, fill=True)
                pdf.set_font("Arial", size=10)
                pdf.cell(190, 8, f" From Category: {cat_orig}", ln=True)
                pdf.cell(190, 8, f" To Category: {cat_dest}", ln=True)
                pdf.ln(5)
                
                # Financials destacados
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(190, 10, " TOTAL ADDITIONAL CHARGE (INCLUDING 30% TAXES)", ln=True)
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(95, 12, f" USD ${total_usd_final:,.2f}", border=1, align='C')
                pdf.cell(95, 12, f" MXN ${total_mxn_final:,.2f}", border=1, ln=True, align='C')
                
                # Texto Legal en Inglés
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
                
                # Espacio para Firmas
                pdf.ln(30)
                y_sig = pdf.get_y()
                pdf.line(10, y_sig, 90, y_sig)
                pdf.line(110, y_sig, 190, y_sig)
                pdf.set_font("Arial", 'B', 9)
                pdf.set_xy(10, y_sig + 2)
                pdf.cell(80, 5, "Guest Signature", align='C')
                pdf.set_xy(110, y_sig + 2)
                pdf.cell(80, 5, "Front Desk Representative", align='C')

                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                st.download_button(f"📥 Download PDF - {cliente}", pdf_bytes, f"Upgrade_{n_reserva}.pdf", "application/pdf")
        else:
            st.error("Error: Upgrade category must be superior to the original (Downgrades not allowed).")
    else:
        st.info("Please select a valid stay range (at least 1 night).")
