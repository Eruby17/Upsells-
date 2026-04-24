import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
import requests
from io import BytesIO

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Cotizador de upsells - Casa Dorada", page_icon="🏨", layout="wide")

# --- 2. IDENTIFICADORES Y URLS ---
SHEET_ID = "19hFs0Jgt58uWC_UXJ8_4aVCJVtX7fTBcHO7-iAVo1K0"
GID_CONFIG = "481323566"  
GID_TARIFAS = "0"          
# URL proporcionada por el usuario
LOGO_URL = "https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e"

def get_csv_url(gid):
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"

@st.cache_data(ttl=600)
def obtener_datos_remotos():
    try:
        df_c = pd.read_csv(get_csv_url(GID_CONFIG))
        df_t = pd.read_csv(get_csv_url(GID_TARIFAS))
        return df_c, df_t
    except:
        return None, None

def procesar_informacion():
    df_1, df_2 = obtener_datos_remotos()
    desc_actual, tc_actual = 62.0, 18.00
    df_tarifas_limpias = pd.DataFrame()

    if df_1 is not None:
        try:
            df_1.columns = [str(c).strip().lower() for c in df_1.columns]
            d_val = df_1[df_1['parametro'].str.contains('descuento', na=False)]['valor'].values[0]
            t_val = df_1[df_1['parametro'].str.contains('tc', na=False)]['valor'].values[0]
            desc_actual = float(str(d_val).replace(',', '.'))
            tc_actual = float(str(t_val).replace(',', '.'))
        except: pass

    if df_2 is not None:
        try:
            df_2.columns = [str(c).strip() for c in df_2.columns]
            df_2['Fecha_Final'] = pd.to_datetime(df_2['Date'], errors='coerce', dayfirst=True).dt.date
            df_2['Rate_Num'] = pd.to_numeric(df_2['Rate'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            df_tarifas_limpias = df_2.dropna(subset=['Fecha_Final', 'Rate_Num']).copy()
        except: pass
        
    return desc_actual, tc_actual, df_tarifas_limpias

desc_actual, tc_actual, df_tarifas = procesar_informacion()

# --- 3. INTERFAZ ---
st.title("🏨 Cotizador de upsells")

col_nom, col_fol = st.columns(2)
with col_nom: cliente = st.text_input("Nombre del Huésped")
with col_fol: n_reserva = st.text_input("Número de Confirmación")

col_in, col_out = st.columns(2)
with col_in: check_in = st.date_input("Check-in", datetime.now().date())
with col_out: check_out = st.date_input("Check-out", datetime.now().date() + timedelta(days=1))
noches = (check_out - check_in).days

diferenciales = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

col_cat1, col_cat2 = st.columns(2)
with col_cat1: cat_orig = st.selectbox("Categoría Original", list(diferenciales.keys()))
with col_cat2: cat_dest = st.selectbox("Upgrade a Categoría", list(diferenciales.keys()), index=1)

st.divider()

# --- 4. CÁLCULOS Y PDF ---
if st.button("💰 Calcular Cotización", type="primary", use_container_width=True):
    if noches <= 0:
        st.error("La fecha de salida debe ser posterior a la de entrada.")
    else:
        with st.spinner("Buscando tarifas..."):
            filtro = df_tarifas[df_tarifas['Fecha_Final'] <= check_in].sort_values('Fecha_Final', ascending=False)
            tarifa_base = float(filtro.iloc[0]['Rate_Num']) if not filtro.empty else 0
            
            gap = diferenciales[cat_dest] - diferenciales[cat_orig]
            precio_noche_usd = (gap * (1 - desc_actual/100)) * 1.30
            total_usd = precio_noche_usd * noches
            total_mxn = total_usd * tc_actual

            # Mostrar resultados en pantalla
            res1, res2, res3 = st.columns(3)
            res1.metric("USD / Noche (Imp. Incl.)", f"${precio_noche_usd:,.2f}")
            res2.metric("Total USD", f"${total_usd:,.2f}")
            res3.metric("Total MXN", f"${total_mxn:,.2f}")

            # --- GENERACIÓN DE PDF ---
            pdf = FPDF()
            pdf.add_page()
            
            # 1. Logo Superior Izquierda (Carga desde URL directa)
            try:
                r = requests.get(LOGO_URL, timeout=10)
                if r.status_code == 200:
                    img = BytesIO(r.content)
                    pdf.image(img, 10, 10, 50) 
            except:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, "CASA DORADA LOS CABOS", ln=True)

            pdf.ln(30)
            
            # 2. Encabezado
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='R')
            pdf.set_font("Arial", '', 10)
            pdf.cell(0, 5, f"Date: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='R')
            pdf.ln(10)

            # 3. Datos del Huésped
            pdf.set_fill_color(30, 55, 110) 
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, "  GUEST INFORMATION", ln=True, fill=True)
            
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", '', 11)
            pdf.ln(2)
            pdf.cell(95, 8, f"Guest: {cliente.upper()}")
            pdf.cell(95, 8, f"Confirmation: {n_reserva}", ln=True)
            pdf.cell(95, 8, f"Check-in: {check_in.strftime('%d %b, %Y')}")
            pdf.cell(95, 8, f"Check-out: {check_out.strftime('%d %b, %Y')}", ln=True)
            pdf.ln(8)

            # 4. Tabla de Upgrade Profesional
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, "  ROOM UPGRADE DETAILS", ln=True, fill=True)
            
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(45, 10, "  Original Room:", border='B', fill=True)
            pdf.set_font("Arial", '', 10)
            pdf.cell(145, 10, f"  {cat_orig}", border='B', ln=True)
            
            pdf.set_fill_color(230, 240, 255) 
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(45, 12, "  UPGRADED TO:", border='B', fill=True)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(145, 12, f"  {cat_dest}", border='B', ln=True)
            pdf.ln(10)

            # 5. Totales
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(120, 10, "Total Upgrade Fee (Including Taxes):", border='T')
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(70, 10, f"USD ${total_usd:,.2f}", border='T', align='R', ln=True)
            
            pdf.set_font("Arial", '', 10)
            pdf.cell(120, 8, f"Charge in Mexican Pesos (T.C. {tc_actual}):")
            pdf.cell(70, 8, f"MXN ${total_mxn:,.2f}*", align='R', ln=True)
            pdf.ln(15)

            # 6. Políticas y Firmas
            pdf.set_font("Arial", 'I', 9)
            pdf.multi_cell(0, 5, "Terms: This upgrade is non-refundable and applies for the entire stay.\nEste upgrade no es reembolsable y aplica por la estancia completa.")
            
            pdf.ln(25)
            pdf.line(10, pdf.get_y(), 85, pdf.get_y())
            pdf.line(125, pdf.get_y(), 200, pdf.get_y())
            pdf.set_font("Arial", '', 10)
            pdf.cell(75, 10, "Guest Signature", align='C')
            pdf.set_x(125)
            pdf.cell(75, 10, "Front Office Representative", align='C')

            # Botón de Descarga
            res_pdf = pdf.output(dest='S').encode('latin-1', errors='replace')
            st.download_button("📥 Descargar PDF", res_pdf, f"Upsell_{n_reserva}.pdf", "application/pdf", use_container_width=True)
