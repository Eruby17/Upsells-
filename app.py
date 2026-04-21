import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARGAR CONFIGURACIÓN (DESCUENTO Y TC) ---
try:
    df_config = conn.read(worksheet="Config", ttl="0") 
    desc_actual = float(df_config.loc[df_config['parametro'] == 'descuento', 'valor'].values[0])
    tc_actual = float(df_config.loc[df_config['parametro'] == 'tc', 'valor'].values[0])
except:
    desc_actual, tc_actual = 55.0, 18.0

# --- CARGAR TARIFAS BASE ---
try:
    df_tarifas = conn.read(worksheet="Tarifas", ttl="1h")
    df_tarifas['Stay Date'] = pd.to_datetime(df_tarifas['Stay Date'])
except:
    df_tarifas = pd.DataFrame()

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
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=150)
    st.header("Strategy Overview")
    st.metric("Web Discount", f"{desc_actual}%")
    st.metric("Exchange Rate", f"${tc_actual} MXN")

# --- INTERFAZ ---
st.title("🏨 Upsell Agreement Generator")

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Guest Name")
    n_reserva = st.text_input("Confirmation Number")
    cat_orig = st.selectbox("Original Category", list(diferenciales_usd.keys()))

with col2:
    rango_fechas = st.date_input("Stay Dates (Check-in to Check-out)", 
                                 value=(datetime.now(), datetime.now() + timedelta(days=1)))
    habitacion = st.text_input("Room Number")
    cat_dest = st.selectbox("Upgrade Category", list(diferenciales_usd.keys()), index=1)

# --- LÓGICA DE CÁLCULO ---
total_noche_mxn_acumulado = 0
total_noche_usd_acumulado = 0
noches = 0

if len(rango_fechas) == 2:
    check_in, check_out = rango_fechas
    noches = (check_out - check_in).days
    
    if noches > 0:
        # Calculamos la diferencia de categoría una sola vez (es constante sobre la base)
        diff_usd_cat = diferenciales_usd[cat_dest] - diferenciales_usd[cat_orig]
        factor_desc = 1 - (desc_actual / 100)
        
        # Iterar por cada noche para validar si hay tarifas específicas (opcional por si cambia el suplemento)
        # En este caso, el diferencial es fijo por categoría, pero aplicamos TC e impuestos
        if diff_usd_cat > 0:
            precio_noche_usd = diff_usd_cat * factor_desc
            precio_noche_mxn = precio_noche_usd * tc_actual * 1.19
            
            total_total_mxn = precio_noche_mxn * noches
            total_total_usd = precio_noche_usd * noches * 1.19
            
            st.divider()
            c1, c2 = st.columns(2)
            c1.metric("Daily Add-on (Inc. Tax)", f"${precio_noche_mxn:,.2f} MXN")
            c2.metric(f"Total for {noches} nights", f"${total_total_mxn:,.2f} MXN")

            # --- GENERADOR DE PDF PROFESIONAL ---
            if st.button("📝 Generate Official Agreement"):
                pdf = FPDF()
                pdf.add_page()
                
                # Header con Logo
                try:
                    pdf.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", 10, 8, 33)
                except: pass
                
                pdf.set_font("Arial", 'B', 15)
                pdf.ln(10)
                pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                pdf.ln(5)
                
                # Guest Info Table
                pdf.set_font("Arial", 'B', 10)
                pdf.set_fill_color(230, 230, 230)
                pdf.cell(190, 7, " GUEST & RESERVATION DETAILS", ln=True, fill=True)
                pdf.set_font("Arial", size=10)
                pdf.cell(95, 8, f" Guest Name: {cliente.upper()}", border='B')
                pdf.cell(95, 8, f" Confirmation: {n_reserva}", border='B', ln=True)
                pdf.cell(95, 8, f" Room Number: {habitacion}", border='B')
                pdf.cell(95, 8, f" Stay: {check_in.strftime('%m/%d/%Y')} - {check_out.strftime('%m/%d/%Y')} ({noches} nights)", border='B', ln=True)
                pdf.ln(5)
                
                # Upgrade Details
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(190, 7, " UPGRADE INFORMATION", ln=True, fill=True)
                pdf.set_font("Arial", size=10)
                pdf.cell(190, 8, f" Original Category: {cat_orig}", ln=True)
                pdf.cell(190, 8, f" New Category: {cat_dest}", ln=True)
                pdf.ln(2)
                
                # Financials
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(190, 10, f" TOTAL ADDITIONAL CHARGE (Including Taxes):", ln=True)
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(95, 12, f" USD ${total_total_usd:,.2f}", border=1, align='C')
                pdf.cell(95, 12, f" MXN ${total_total_mxn:,.2f}", border=1, ln=True, align='C')
                
                pdf.set_font("Arial", size=9)
                pdf.ln(5)
                pdf.multi_cell(0, 5, "By signing this document, I agree to the room category change and the additional charges mentioned above. I authorize Casa Dorada Los Cabos Resort & Spa to post these charges to my room account. I understand that the final amount in Mexican Pesos may vary slightly based on the hotel's internal exchange rate at the time of checkout.")
                
                # Signature Section
                pdf.ln(25)
                y_sig = pdf.get_y()
                pdf.line(10, y_sig, 90, y_sig)
                pdf.line(110, y_sig, 190, y_sig)
                pdf.set_y(y_sig + 2)
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(80, 5, "Guest Signature", align='C')
                pdf.set_x(110)
                pdf.cell(80, 5, "Front Desk Representative", align='C')
                
                # Footer
                pdf.set_y(-25)
                pdf.set_font("Arial", 'I', 8)
                pdf.cell(0, 5, "Casa Dorada Los Cabos Resort & Spa - Upsell Official Form", align='C', ln=True)

                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                st.download_button(f"📥 Download Agreement - {cliente}", pdf_bytes, f"Upsell_{n_reserva}.pdf", "application/pdf")
        else:
            st.error("No se permiten downgrades.")
