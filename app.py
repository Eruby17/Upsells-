import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARGAR CONFIGURACIÓN (Descuento y TC) ---
try:
    df_config = conn.read(worksheet="Config", ttl=0)
    df_config.columns = df_config.columns.str.strip().str.lower()
    df_config['parametro'] = df_config['parametro'].astype(str).str.strip().str.lower()
    
    desc_actual = float(df_config[df_config['parametro'] == 'descuento']['valor'].values[0])
    tc_actual = float(df_config[df_config['parametro'] == 'tc']['valor'].values[0])
except:
    desc_actual, tc_actual = 62.0, 17.40

# --- CARGAR TARIFAS BASE DEL DÍA ---
try:
    df_tarifas = conn.read(worksheet="Tarifas", ttl=0)
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

# --- INTERFAZ ---
st.title("🏨 Professional Upsell Calculator")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.metric("Web Discount", f"{desc_actual}%")
    st.metric("Exchange Rate", f"${tc_actual} MXN")
    if st.button("🔄 Sync Drive"):
        st.cache_data.clear()
        st.rerun()

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Guest Name")
    cat_orig = st.selectbox("Original Category", list(diferenciales_usd.keys()))
    fecha_estancia = st.date_input("Stay Date", datetime.now())

with col2:
    n_reserva = st.text_input("Confirmation #")
    cat_dest = st.selectbox("Upgrade Category", list(diferenciales_usd.keys()), index=3)
    noches = st.number_input("Nights", min_value=1, value=1)

# --- LÓGICA DE CÁLCULO POR PASOS ---
# 1. Obtener Tarifa Base del Drive
tarifa_base_usd = 0
if not df_tarifas.empty:
    res = df_tarifas[df_tarifas['Stay Date'] == pd.to_datetime(fecha_estancia)]
    if not res.empty:
        tarifa_base_usd = float(res.iloc[0]['Current Rate'])

if tarifa_base_usd > 0:
    # 2. Calcular Totales con diferenciales
    precio_original_base = tarifa_base_usd + diferenciales_usd[cat_orig]
    precio_upgrade_base = tarifa_base_usd + diferenciales_usd[cat_dest]
    
    # 3. Diferencia Bruta (Antes de descuento e impuestos)
    diferencial_bruto = precio_upgrade_base - precio_original_base
    
    if diferencial_bruto > 0:
        # 4. Aplicar Descuento
        factor_desc = 1 - (desc_actual / 100)
        precio_con_descuento = diferencial_bruto * factor_desc
        
        # 5. Aplicar Impuestos (30%)
        precio_final_usd_noche = precio_con_descuento * 1.30
        
        # Totales Estancia
        total_usd_estancia = precio_final_usd_noche * noches
        total_mxn_estancia = total_usd_estancia * tc_actual

        # --- MOSTRAR RESULTADOS ---
        st.divider()
        st.info(f"Base Rate for {fecha_estancia.strftime('%Y-%m-%d')}: ${tarifa_base_usd:,.2f} USD")
        
        c1, c2 = st.columns(2)
        c1.metric("Total Upgrade USD (Inc. 30% Tax)", f"${total_usd_estancia:,.2f}")
        c2.metric("Total Upgrade MXN (Inc. 30% Tax)", f"${total_mxn_estancia:,.2f}")

        # --- GENERADOR DE PDF ---
        if st.button("📋 Generate Agreement"):
            pdf = FPDF()
            pdf.add_page()
            try: pdf.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", 10, 8, 45)
            except: pass
            
            pdf.ln(15); pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='R')
            pdf.ln(10)
            
            pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(245, 245, 245)
            pdf.cell(190, 8, " RESERVATION DETAILS", ln=True, fill=True)
            pdf.set_font("Arial", size=10)
            pdf.cell(95, 8, f" Guest: {cliente.upper()}", border='B')
            pdf.cell(95, 8, f" Confirmation: {n_reserva}", border='B', ln=True)
            pdf.cell(190, 8, f" Category: {cat_orig}  >>>  {cat_dest}", border='B', ln=True)
            pdf.ln(10)
            
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(190, 10, " TOTAL ADDITIONAL CHARGE (30% TAX INCLUDED)", ln=True)
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(95, 12, f" USD ${total_usd_estancia:,.2f}", border=1, align='C')
            pdf.cell(95, 12, f" MXN ${total_mxn_estancia:,.2f}", border=1, ln=True, align='C')
            
            pdf.ln(10); pdf.set_font("Arial", size=9)
            pdf.multi_cell(0, 5, "I authorize Casa Dorada Los Cabos to post these charges to my room account. Final charges in MXN are subject to the hotel's exchange rate at checkout.")
            
            pdf.ln(30)
            y = pdf.get_y(); pdf.line(10, y, 90, y); pdf.line(110, y, 190, y)
            pdf.set_y(y + 2); pdf.cell(80, 5, "Guest Signature", align='C')
            pdf.set_x(110); pdf.cell(80, 5, "Front Desk Agent", align='C')

            st.download_button("📥 Download PDF", pdf.output(dest='S').encode('latin-1'), f"Upgrade_{n_reserva}.pdf", "application/pdf")
    else:
        st.error("The selected category is not an upgrade.")
else:
    st.warning("No base rate found for this date in the 'Tarifas' sheet.")
