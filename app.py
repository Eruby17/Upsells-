import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
import requests
from io import BytesIO

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨", layout="wide")

# --- 2. IDENTIFICADORES DE HOJA (SEGÚN TUS DATOS) ---
SHEET_ID = "19hFs0Jgt58uWC_UXJ8_4aVCJVtX7fTBcHO7-iAVo1K0"
GID_CONFIG = "481323566"  # Pestaña 1
GID_TARIFAS = "0"          # Pestaña 2
LOGO_URL = "https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e"

def get_csv_url(gid):
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"

# --- 3. CARGA DE DATOS ---
@st.cache_data(ttl=0)
def cargar_datos_directos():
    try:
        df_c = pd.read_csv(get_csv_url(GID_CONFIG))
        df_t = pd.read_csv(get_csv_url(GID_TARIFAS))
        return df_c, df_t
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None, None

df_1, df_2 = cargar_datos_directos()

# --- 4. PROCESAMIENTO DE VALORES (SIDEBAR) ---
desc_actual, tc_actual = 62.0, 17.40 

if df_1 is not None:
    try:
        df_1.columns = [str(c).strip().lower() for c in df_1.columns]
        d_val = df_1[df_1['parametro'].str.contains('descuento', case=False, na=False)]['valor'].values[0]
        t_val = df_1[df_1['parametro'].str.contains('tc', case=False, na=False)]['valor'].values[0]
        desc_actual = float(str(d_val).replace(',', '.'))
        tc_actual = float(str(t_val).replace(',', '.'))
    except:
        pass

df_tarifas = pd.DataFrame()
if df_2 is not None:
    try:
        df_2.columns = [str(c).strip() for c in df_2.columns]
        df_2['Fecha_DT'] = pd.to_datetime(df_2['Date'], dayfirst=True, errors='coerce').dt.date
        df_2['Rate_Num'] = pd.to_numeric(df_2['Rate'].astype(str).str.replace(',', '.'), errors='coerce')
        df_tarifas = df_2.dropna(subset=['Fecha_DT', 'Rate_Num'])
    except:
        pass

# --- 5. INTERFAZ ---
st.title("🏨 Professional Upsell Agreement")

with st.sidebar:
    st.image(LOGO_URL, width=180)
    st.metric("Web Discount", f"{desc_actual}%")
    st.metric("FX Rate", f"${tc_actual} MXN")
    if st.button("🔄 Sync with Drive"):
        st.cache_data.clear()
        st.rerun()

diferenciales = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

# Bloque 1: Información del Huésped
col_nom, col_fol = st.columns(2)
with col_nom:
    cliente = st.text_input("Guest Full Name")
with col_fol:
    n_reserva = st.text_input("Confirmation / Folio #")

# Bloque 2: Categorías (Misma altura)
col_cat1, col_cat2 = st.columns(2)
with col_cat1:
    cat_orig = st.selectbox("Original Category", list(diferenciales.keys()))
with col_cat2:
    cat_dest = st.selectbox("Upgrade Category", list(diferenciales.keys()), index=3)

# Bloque 3: Fechas (Rango) y Habitación
col_fec, col_hab = st.columns(2)
with col_fec:
    # Selección de rango: Check-in y Check-out
    rango = st.date_input("Stay Period (Select Check-in & Check-out)", 
                          value=(datetime.now().date(), (datetime.now() + timedelta(days=1)).date()))
with col_hab:
    habitacion = st.text_input("Assigned Room #")

# --- 6. CÁLCULOS ---
if len(rango) == 2:
    arrival, departure = rango
    noches = (departure - arrival).days
    
    if noches > 0:
        tarifa_base = 0
        if not df_tarifas.empty:
            # Buscamos la tarifa basada en el día de llegada
            match = df_tarifas[df_tarifas['Fecha_DT'] == arrival]
            if not match.empty:
                tarifa_base = float(match.iloc[0]['Rate_Num'])
        
        if tarifa_base <= 0:
            st.error(f"❌ No rate found for {arrival.strftime('%d/%m/%Y')} in Excel.")
        else:
            # Lógica: (Upg - Orig) -> Descuento -> Impuestos (30%)
            monto_orig = tarifa_base + diferenciales[cat_orig]
            monto_upg = tarifa_base + diferenciales[cat_dest]
            gap = monto_upg - monto_orig
            
            if gap > 0:
                final_night_usd = (gap * (1 - desc_actual/100)) * 1.30
                total_usd = final_night_usd * noches
                total_mxn = total_usd * tc_actual

                st.divider()
                st.success(f"Stay of {noches} night(s) calculated.")
                res1, res2 = st.columns(2)
                res1.metric("Total USD (Inc. Tax)", f"${total_usd:,.2f}")
                res2.metric("Total MXN (Inc. Tax)", f"${total_mxn:,.2f}")

                # --- 7. GENERACIÓN DE PDF ---
                if st.button("📝 Generate Official Agreement PDF"):
                    pdf = FPDF()
                    pdf.add_page()
                    
                    # Insertar Logo desde URL
                    try:
                        response = requests.get(LOGO_URL)
                        logo_img = BytesIO(response.content)
                        pdf.image(logo_img, 10, 8, 45)
                    except:
                        pass
                    
                    pdf.ln(20)
                    pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                    pdf.ln(10)
                    
                    # Tabla de Detalles
                    pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(240, 240, 240)
                    pdf.cell(190, 8, " RESERVATION DETAILS", ln=True, fill=True)
                    pdf.set_font("Arial", size=10)
                    pdf.cell(95, 8, f" Guest: {cliente.upper()}", border='B')
                    pdf.cell(95, 8, f" Confirmation: {n_reserva}", border='B', ln=True)
                    pdf.cell(95, 8, f" Arrival: {arrival.strftime('%d/%m/%Y')}", border='B')
                    pdf.cell(95, 8, f" Departure: {departure.strftime('%d/%m/%Y')}", border='B', ln=True)
                    pdf.cell(95, 8, f" Nights: {noches}", border='B')
                    pdf.cell(95, 8, f" Room: {habitacion}", border='B', ln=True)
                    pdf.ln(10)
                    
                    # Categorías
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(190, 8, f" Original Category: {cat_orig}", ln=True)
                    pdf.cell(190, 8, f" Upgraded to: {cat_dest}", ln=True)
                    pdf.ln(10)
                    
                    # Totales
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(95, 12, f" TOTAL USD ${total_usd:,.2f}", border=1, align='C')
                    pdf.cell(95, 12, f" TOTAL MXN ${total_mxn:,.2f}", border=1, ln=True, align='C')
                    
                    # Firmas
                    pdf.ln(30)
                    y_pos = pdf.get_y()
                    pdf.line(10, y_pos, 90, y_pos)
                    pdf.line(110, y_pos, 190, y_pos)
                    pdf.set_y(y_pos + 2)
                    pdf.set_font("Arial", 'B', 9)
                    pdf.cell(80, 5, "Guest Signature", align='C')
                    pdf.set_x(110)
                    pdf.cell(80, 5, "Front Desk Representative", align='C')

                    # Descarga
                    st.download_button("📥 Download PDF Agreement", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf")
            else:
                st.warning("Please select a superior category for the upgrade.")
    else:
        st.error("Error: Departure date must be after arrival date.")
else:
    st.info("Please select both check-in and check-out dates on the calendar.")
