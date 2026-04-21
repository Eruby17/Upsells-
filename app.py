import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import re

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

# --- CARGAR TARIFAS BASE CON LIMPIEZA DE FECHA ---
try:
    df_tarifas = conn.read(worksheet="Tarifas", ttl=0)
    
    def limpiar_fecha(texto):
        texto = str(texto)
        match = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
        return match.group(1) if match else texto

    df_tarifas['Stay Date'] = df_tarifas['Stay Date'].apply(limpiar_fecha)
    df_tarifas['Stay Date'] = pd.to_datetime(df_tarifas['Stay Date'], dayfirst=True).dt.date
except Exception as e:
    df_tarifas = pd.DataFrame()
    st.error(f"Error procesando las fechas del Excel: {e}")

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
st.title("🏨 Room Upgrade Agreement")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.metric("Descuento Aplicado", f"{desc_actual}%")
    st.metric("Tipo de Cambio", f"${tc_actual} MXN")
    if st.button("🔄 Sincronizar Drive"):
        st.cache_data.clear()
        st.rerun()

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Nombre del Huésped")
    cat_orig = st.selectbox("Categoría Original", list(diferenciales_usd.keys()))
    rango_fechas = st.date_input(
        "Fechas de Estancia (Llegada y Salida)",
        value=(datetime.now().date(), (datetime.now() + timedelta(days=1)).date()),
        min_value=datetime.now().date()
    )

with col2:
    n_reserva = st.text_input("Confirmación / Folio #")
    cat_dest = st.selectbox("Categoría de Upgrade", list(diferenciales_usd.keys()), index=3)
    habitacion = st.text_input("Número de Habitación")

# --- PROCESAMIENTO Y CÁLCULO ---
if len(rango_fechas) == 2:
    check_in, check_out = rango_fechas
    noches = (check_out - check_in).days
    
    if noches > 0:
        tarifa_base_usd = 0
        fecha_encontrada = False
        
        if not df_tarifas.empty:
            res = df_tarifas[df_tarifas['Stay Date'] == check_in]
            if not res.empty:
                tarifa_base_usd = float(res.iloc[0]['Current Rate'])
                fecha_encontrada = True
        
        # --- CONTROL DE ERROR SI NO HAY TARIFA CARGADA ---
        if not fecha_encontrada:
            st.error(f"❌ ERROR CRÍTICO: No se encontraron tarifas cargadas para el mes de {check_in.strftime('%B %Y')}. Por favor, carga el tarifario en la pestaña 'Tarifas' antes de continuar.")
        else:
            # LÓGICA DE CÁLCULO
            precio_orig_total = tarifa_base_usd + diferenciales_usd[cat_orig]
            precio_upg_total = tarifa_base_usd + diferenciales_usd[cat_dest]
            diff_bruta = precio_upg_total - precio_orig_total
            
            if diff_bruta > 1:
                factor_desc = 1 - (desc_actual / 100)
                precio_con_desc = diff_bruta * factor_desc
                precio_final_noche_usd = precio_con_desc * 1.30
                
                total_usd = precio_final_noche_usd * noches
                total_mxn = total_usd * tc_actual

                st.divider()
                st.success(f"Estancia de {noches} noche(s) calculada correctamente.")
                
                c1, c2 = st.columns(2)
                c1.metric("Total Upgrade USD (30% Tax Inc.)", f"${total_usd:,.2f}")
                c2.metric("Total Upgrade MXN (30% Tax Inc.)", f"${total_mxn:,.2f}")

                # --- GENERADOR DE PDF ---
                if st.button("📝 Generar Formato PDF"):
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
                    pdf.cell(95, 8, f" Arrival: {check_in.strftime('%d/%m/%Y')}", border='B')
                    pdf.cell(95, 8, f" Departure: {check_out.strftime('%d/%m/%Y')}", border='B', ln=True)
                    pdf.cell(95, 8, f" Room: {habitacion}", border='B')
                    pdf.cell(95, 8, f" Total Nights: {noches}", border='B', ln=True)
                    pdf.ln(5)
                    
                    pdf.set_font("Arial", 'B', 10)
                    pdf.cell(190, 8, " UPGRADE INFORMATION", ln=True, fill=True)
                    pdf.set_font("Arial", size=10)
                    pdf.cell(190, 8, f" From Category: {cat_orig}", ln=True)
                    pdf.cell(190, 8, f" To Category: {cat_dest}", ln=True)
                    pdf.ln(10)
                    
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(190, 10, " TOTAL ADDITIONAL CHARGE (30% TAX INCLUDED)", ln=True)
                    pdf.set_font("Arial", 'B', 15)
                    pdf.cell(95, 15, f" USD ${total_usd:,.2f}", border=1, align='C')
                    pdf.cell(95, 15, f" MXN ${total_mxn:,.2f}", border=1, ln=True, align='C')
                    
                    pdf.ln(10); pdf.set_font("Arial", size=9)
                    pdf.multi_cell(0, 5, "I authorize Casa Dorada Los Cabos Resort & Spa to apply these additional charges to my room account. I understand that the total in MXN may vary according to the hotel's exchange rate at the time of payment.")
                    
                    pdf.ln(30)
                    y = pdf.get_y(); pdf.line(10, y, 90, y); pdf.line(110, y, 190, y)
                    pdf.set_y(y + 2); pdf.cell(80, 5, "Guest Signature", align='C')
                    pdf.set_x(110); pdf.cell(80, 5, "Front Desk Representative", align='C')

                    st.download_button("📥 Descargar Acuerdo PDF", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf", "application/pdf")
            else:
                st.warning("⚠️ La categoría seleccionada no representa un upgrade económico sobre la tarifa base.")
    else:
        st.info("Selecciona el día de llegada y el día de salida en el calendario.")
