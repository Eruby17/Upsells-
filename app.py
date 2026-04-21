import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import re

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. CARGAR CONFIGURACIÓN (Descuento y TC desde pestaña 'Config') ---
try:
    df_config = conn.read(worksheet="Config", ttl=0)
    df_config.columns = df_config.columns.str.strip().str.lower()
    df_config['parametro'] = df_config['parametro'].astype(str).str.strip().str.lower()
    
    desc_actual = float(df_config[df_config['parametro'] == 'descuento']['valor'].values[0])
    tc_actual = float(df_config[df_config['parametro'] == 'tc']['valor'].values[0])
except Exception:
    desc_actual, tc_actual = 62.0, 17.40 # Respaldo según tu captura

# --- 4. CARGAR TARIFAS CON LIMPIEZA ULTRA-ROBUSTA ---
try:
    df_tarifas = conn.read(worksheet="Tarifas", ttl=0)
    
    def limpiar_fecha_pro(texto):
        texto = str(texto).strip()
        # Busca cualquier patrón DD/MM/YYYY o D/M/YYYY ignorando el texto del día (mié, jue)
        match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', texto)
        return match.group(1) if match else None

    df_tarifas['Stay Date Clean'] = df_tarifas['Stay Date'].apply(limpiar_fecha_pro)
    df_tarifas = df_tarifas.dropna(subset=['Stay Date Clean'])
    df_tarifas['Stay Date Clean'] = pd.to_datetime(df_tarifas['Stay Date Clean'], dayfirst=True).dt.date
except Exception as e:
    df_tarifas = pd.DataFrame()
    st.error(f"Error procesando el tarifario: {e}")

# --- 5. DIFERENCIALES DUETTO (USD) ---
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

# --- 6. BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.header("Revenue Strategy")
    st.metric("Web Discount", f"{desc_actual}%")
    st.metric("Exchange Rate", f"${tc_actual} MXN")
    if st.button("🔄 Sync with Drive"):
        st.cache_data.clear()
        st.rerun()

# --- 7. INTERFAZ PRINCIPAL ---
st.title("🏨 Room Upgrade Agreement")

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Guest Full Name")
    cat_orig = st.selectbox("Original Category", list(diferenciales_usd.keys()))
    rango_fechas = st.date_input(
        "Stay Dates",
        value=(datetime.now().date(), (datetime.now() + timedelta(days=1)).date()),
        min_value=datetime.now().date()
    )

with col2:
    n_reserva = st.text_input("Confirmation / Folio #")
    cat_dest = st.selectbox("Upgrade Category", list(diferenciales_usd.keys()), index=3)
    habitacion = st.text_input("Assigned Room #")

# --- 8. PROCESAMIENTO Y LÓGICA FINANCIERA ---
if len(rango_fechas) == 2:
    check_in, check_out = rango_fechas
    noches = (check_out - check_in).days
    
    if noches > 0:
        tarifa_base_usd = 0
        if not df_tarifas.empty:
            # Buscamos la tarifa en la columna limpia
            res = df_tarifas[df_tarifas['Stay Date Clean'] == check_in]
            if not res.empty:
                tarifa_base_usd = float(res.iloc[0]['Current Rate'])
            else:
                st.error(f"❌ ERROR CRÍTICO: No base rate found for {check_in.strftime('%d/%m/%Y')}. Please update the 'Tarifas' sheet.")
        
        if tarifa_base_usd > 0:
            # PASO 1: Calcular totales con diferenciales
            total_original_noche = tarifa_base_usd + diferenciales_usd[cat_orig]
            total_upgrade_noche = tarifa_base_usd + diferenciales_usd[cat_dest]
            
            # PASO 2: Diferencia Bruta
            diff_bruta = total_upgrade_noche - total_original_noche
            
            if diff_bruta > 0:
                # PASO 3: Aplicar Descuento (ej. 62%)
                factor_desc = 1 - (desc_actual / 100)
                precio_con_desc = diff_bruta * factor_desc
                
                # PASO 4: Aplicar Impuestos (30%)
                precio_noche_final_usd = precio_con_desc * 1.30
                
                # Totales Finales
                total_usd_estancia = precio_noche_final_usd * noches
                total_mxn_estancia = total_usd_estancia * tc_actual

                st.divider()
                st.success(f"Stay of {noches} night(s) calculated successfully.")
                c1, c2 = st.columns(2)
                c1.metric("Total USD (30% Tax Inc.)", f"${total_usd_estancia:,.2f}")
                c2.metric("Total MXN (30% Tax Inc.)", f"${total_mxn_estancia:,.2f}")

                # --- 9. GENERADOR DE PDF ---
                if st.button("📝 Generate PDF Agreement"):
                    pdf = FPDF()
                    pdf.add_page()
                    try: pdf.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", 10, 8, 45)
                    except: pass
                    
                    pdf.ln(15); pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='R')
                    pdf.ln(10)
                    
                    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(245, 245, 245)
                    pdf.cell(190, 8, " RESERVATION & STAY DETAILS", ln=True, fill=True)
                    pdf.set_font("Arial", size=10)
                    pdf.cell(95, 8, f" Guest: {cliente.upper()}", border='B')
                    pdf.cell(95, 8, f" Confirmation: {n_reserva}", border='B', ln=True)
                    pdf.cell(95, 8, f" Arrival: {check_in.strftime('%b %d, %Y')}", border='B')
                    pdf.cell(95, 8, f" Departure: {check_out.strftime('%b %d, %Y')}", border='B', ln=True)
                    pdf.cell(95, 8, f" Room: {habitacion}", border='B')
                    pdf.cell(95, 8, f" Total Nights: {noches}", border='B', ln=True)
                    pdf.ln(5)
                    
                    pdf.set_font("Arial", 'B', 10)
                    pdf.cell(190, 8, " UPGRADE INFORMATION", ln=True, fill=True)
                    pdf.set_font("Arial", size=10)
                    pdf.cell(190, 8, f" From: {cat_orig}", ln=True)
                    pdf.cell(190, 8, f" To: {cat_dest}", ln=True)
                    pdf.ln(10)
                    
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(190, 10, " TOTAL ADDITIONAL CHARGE (30% TAXES INCLUDED)", ln=True)
                    pdf.set_font("Arial", 'B', 15)
                    pdf.cell(95, 15, f" USD ${total_usd_estancia:,.2f}", border=1, align='C')
                    pdf.cell(95, 15, f" MXN ${total_mxn_estancia:,.2f}", border=1, ln=True, align='C')
                    
                    pdf.ln(10); pdf.set_font("Arial", size=9)
                    pdf.multi_cell(0, 5, "I authorize Casa Dorada Los Cabos to post these charges to my room account. Final charges in MXN are subject to the hotel's exchange rate at checkout.")
                    
                    pdf.ln(30)
                    y = pdf.get_y(); pdf.line(10, y, 90, y); pdf.line(110, y, 190, y)
                    pdf.set_y(y + 2); pdf.cell(80, 5, "Guest Signature", align='C')
                    pdf.set_x(110); pdf.cell(80, 5, "Front Desk Representative", align='C')

                    st.download_button("📥 Download PDF", pdf.output(dest='S').encode('latin-1'), f"Upgrade_{n_reserva}.pdf", "application/pdf")
            else:
                st.warning("⚠️ No financial upgrade detected. Selected category is cheaper or equal to original.")
    else:
        st.info("Select Arrival and Departure dates in the calendar.")
