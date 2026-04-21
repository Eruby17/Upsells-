import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
import requests
from io import BytesIO

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Cotizador de upsells - Casa Dorada", page_icon="🏨", layout="wide")

# --- 2. IDENTIFICADORES ---
SHEET_ID = "19hFs0Jgt58uWC_UXJ8_4aVCJVtX7fTBcHO7-iAVo1K0"
GID_CONFIG = "481323566"  
GID_TARIFAS = "0"          
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

# --- 4. PROCESAMIENTO SIDEBAR ---
desc_actual, tc_actual = 62.0, 17.40 
if df_1 is not None:
    try:
        df_1.columns = [str(c).strip().lower() for c in df_1.columns]
        d_val = df_1[df_1['parametro'].str.contains('descuento', case=False, na=False)]['valor'].values[0]
        t_val = df_1[df_1['parametro'].str.contains('tc', case=False, na=False)]['valor'].values[0]
        desc_actual = float(str(d_val).replace(',', '.'))
        tc_actual = float(str(t_val).replace(',', '.'))
    except: pass

# --- MOTOR DE TARIFAS ---
df_tarifas = pd.DataFrame()
if df_2 is not None:
    try:
        df_2.columns = [str(c).strip() for c in df_2.columns]
        df_2['Fecha_Final'] = pd.to_datetime(df_2['Date'], errors='coerce', dayfirst=True).dt.date
        df_2['Rate_Num'] = pd.to_numeric(df_2['Rate'].astype(str).str.replace(',', '.').str.extract('(\d+\.?\d*)')[0], errors='coerce')
        df_tarifas = df_2.dropna(subset=['Fecha_Final', 'Rate_Num']).copy()
    except: pass

# --- 5. INTERFAZ ---
st.title("🏨 Cotizador de upsells")

with st.sidebar:
    st.image(LOGO_URL, width=150)
    st.metric("Descuento Aplicado", f"{desc_actual}%")
    st.metric("T.C. del día", f"${tc_actual} MXN")
    if st.button("🔄 Sincronizar"):
        st.cache_data.clear()
        st.rerun()

diferenciales = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

# Bloque 1: Huésped
col_nom, col_fol = st.columns(2)
with col_nom: cliente = st.text_input("Nombre del Huésped")
with col_fol: n_reserva = st.text_input("Número de Confirmación / Folio")

# Bloque 2: Categorías
col_cat1, col_cat2 = st.columns(2)
with col_cat1: cat_orig = st.selectbox("Categoría Original", list(diferenciales.keys()))
with col_cat2: cat_dest = st.selectbox("Upgrade a Categoría", list(diferenciales.keys()), index=3)

# Bloque 3: Fechas
col_in, col_out = st.columns(2)
with col_in: check_in = st.date_input("Fecha de Entrada (Check-in)", datetime.now().date())
with col_out: check_out = st.date_input("Fecha de Salida (Check-out)", datetime.now().date() + timedelta(days=1))

# --- 6. CÁLCULOS ---
noches = (check_out - check_in).days

if noches > 0:
    tarifa_base = 0
    if not df_tarifas.empty:
        match = df_tarifas[df_tarifas['Fecha_Final'] == check_in]
        if not match.empty:
            tarifa_base = float(match.iloc[0]['Rate_Num'])
    
    if tarifa_base <= 0:
        st.error(f"❌ No se encontró tarifa para {check_in.strftime('%d/%m/%Y')} en el archivo.")
    else:
        gap = (tarifa_base + diferenciales[cat_dest]) - (tarifa_base + diferenciales[cat_orig])
        if gap > 0:
            final_night_usd = (gap * (1 - desc_actual/100)) * 1.30
            total_usd = final_night_usd * noches
            total_mxn = total_usd * tc_actual

            st.divider()
            st.success(f"Estancia de {noches} noche(s) calculada.")
            res1, res2, res3 = st.columns(3)
            res1.metric("USD / Noche (Imp. Incl.)", f"${final_night_usd:,.2f}")
            res2.metric("Total USD", f"${total_usd:,.2f}")
            res3.metric("Total MXN", f"${total_mxn:,.2f}")

            # --- 7. GENERACIÓN DE PDF ---
            if st.button("📝 Generar Acuerdo PDF"):
                pdf = FPDF()
                pdf.add_page()
                
                # Carga de logo
                try:
                    response = requests.get(LOGO_URL, timeout=10)
                    img = BytesIO(response.content)
                    pdf.image(img, 10, 8, 50)
                except:
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, "CASA DORADA LOS CABOS", ln=True)

                pdf.ln(25)
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                pdf.ln(5)
                
                # Datos Reservación
                pdf.set_font("Arial", 'B', 10); pdf.set_fill_color(240, 240, 240)
                pdf.cell(190, 8, " DETALLES DEL HUESPED Y RESERVACION", ln=True, fill=True)
                pdf.set_font("Arial", size=10)
                pdf.cell(95, 8, f" Guest Name: {cliente.upper()}", border='B')
                pdf.cell(95, 8, f" Confirmation #: {n_reserva}", border='B', ln=True)
                pdf.cell(63, 8, f" Arrival: {check_in.strftime('%d/%m/%Y')}", border='B')
                pdf.cell(63, 8, f" Departure: {check_out.strftime('%d/%m/%Y')}", border='B')
                pdf.cell(64, 8, f" Total Nights: {noches}", border='B', ln=True)
                pdf.ln(8)

                # Categorías
                pdf.set_font("Arial", 'B', 10); pdf.cell(190, 8, " DETALLES DEL UPGRADE", ln=True, fill=True)
                pdf.set_font("Arial", size=11)
                pdf.cell(190, 10, f" Original Category: {cat_orig}", ln=True)
                pdf.cell(190, 10, f" Upgrade Category: {cat_dest}", ln=True)
                pdf.ln(5)

                # Desglose Financiero
                pdf.set_font("Arial", 'B', 11)
                pdf.cell(190, 10, " RESUMEN DE PAGO", ln=True)
                pdf.set_font("Arial", size=11)
                pdf.cell(95, 10, f" Upgrade per Night (Inc. Tax):", border='TL')
                pdf.cell(95, 10, f" USD ${final_night_usd:,.2f}", border='TR', ln=True, align='R')
                
                pdf.set_font("Arial", 'B', 13)
                pdf.cell(95, 12, f" TOTAL AMOUNT DUE:", border='LB')
                pdf.cell(95, 12, f" USD ${total_usd:,.2f} / MXN ${total_mxn:,.2f}*", border='RB', ln=True, align='R')
                pdf.set_font("Arial", 'I', 8)
                pdf.cell(190, 5, f"*Tipo de cambio aplicado: 1 USD = {tc_actual} MXN", ln=True, align='R')
                
                # Políticas
                pdf.ln(10)
                pdf.set_font("Arial", 'B', 10); pdf.set_text_color(200, 0, 0)
                pdf.cell(190, 8, " POLITICAS IMPORTANTES / IMPORTANT POLICIES:", ln=True)
                pdf.set_font("Arial", size=9); pdf.set_text_color(0, 0, 0)
                pdf.multi_cell(190, 5, "Este upgrade es NO REEMBOLSABLE. En caso de cancelacion o modificacion de la estancia, el cargo por mejora de habitacion no sera acreditado ni devuelto.\n\nThis upgrade is NON-REFUNDABLE. In case of cancellation or modification of the stay, the upgrade fee will not be credited or refunded.")
                
                # Firmas
                pdf.ln(25)
                y_sig = pdf.get_y()
                pdf.line(10, y_sig, 90, y_sig)
                pdf.line(110, y_sig, 190, y_sig)
                pdf.set_y(y_sig + 2)
                pdf.set_font("Arial", 'B', 9)
                pdf.cell(80, 5, "Guest Signature", align='C')
                pdf.set_x(110)
                pdf.cell(80, 5, "Hotel Representative", align='C')

                st.download_button("📥 Descargar Acuerdo PDF", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf")
        else:
            st.warning("La categoría de destino debe ser superior a la original para realizar una cotización.")
else:
    st.error("La fecha de salida debe ser posterior a la fecha de entrada.")
