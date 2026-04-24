import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
import requests
from io import BytesIO

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Cotizador Casa Dorada", page_icon="🏨", layout="wide")

# --- 2. IDENTIFICADORES Y URLS ---
SHEET_ID = "19hFs0Jgt58uWC_UXJ8_4aVCJVtX7fTBcHO7-iAVo1K0"
GID_CONFIG = "481323566"  
GID_TARIFAS = "0"          
# URL del logo proporcionada (Raw GitHub)
LOGO_URL = "https://github.com/Eruby17/Upsells-/blob/main/logo%2012.png?raw=true"

def get_csv_url(gid):
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"

# --- 3. SISTEMA DE CACHÉ PERSISTENTE ---
@st.cache_data(ttl=600)
def obtener_datos_remotos():
    try:
        df_c = pd.read_csv(get_csv_url(GID_CONFIG))
        df_t = pd.read_csv(get_csv_url(GID_TARIFAS))
        return df_c, df_t
    except Exception as e:
        st.error(f"Error de conexión: {e}")
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

# --- 4. INTERFAZ DE USUARIO ---
st.title("🏨 Cotizador de Upsells")

with st.sidebar:
    st.image(LOGO_URL, width=150)
    st.metric("Descuento Web", f"{desc_actual}%")
    st.metric("T.C. (MXN)", f"${tc_actual}")
    if st.button("🔄 Actualizar Datos"):
        st.cache_data.clear()
        st.rerun()

diferenciales = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

col_nom, col_fol = st.columns(2)
with col_nom: cliente = st.text_input("Nombre del Huésped")
with col_fol: n_reserva = st.text_input("Número de Confirmación")

col_in, col_out = st.columns(2)
with col_in: check_in = st.date_input("Check-in", datetime.now().date())
with col_out: check_out = st.date_input("Check-out", datetime.now().date() + timedelta(days=1))

col_cat1, col_cat2 = st.columns(2)
with col_cat1: cat_orig = st.selectbox("Categoría Original", list(diferenciales.keys()))
with col_cat2: cat_dest = st.selectbox("Upgrade a", list(diferenciales.keys()), index=1)

st.divider()

# --- 5. LÓGICA DE CÁLCULO ---
if st.button("💰 Calcular y Generar Cotización", type="primary", use_container_width=True):
    with st.spinner("Procesando tarifas..."):
        noches = (check_out - check_in).days
        
        if noches <= 0:
            st.error("La fecha de salida debe ser posterior a la de entrada.")
        elif df_tarifas.empty:
            st.error("No hay datos de tarifas disponibles.")
        else:
            filtro = df_tarifas[df_tarifas['Fecha_Final'] <= check_in].sort_values('Fecha_Final', ascending=False)
            
            if filtro.empty:
                st.warning("No se encontró tarifa para la fecha seleccionada.")
            else:
                tarifa_base = float(filtro.iloc[0]['Rate_Num'])
                gap = diferenciales[cat_dest] - diferenciales[cat_orig]
                
                if gap <= 0:
                    st.warning("Seleccione una categoría superior para el Upgrade.")
                else:
                    precio_noche_usd = (gap * (1 - desc_actual/100)) * 1.30
                    total_usd = precio_noche_usd * noches
                    total_mxn = total_usd * tc_actual

                    # Mostrar resultados en pantalla
                    c1, c2, c3 = st.columns(3)
                    c1.metric("USD / Noche", f"${precio_noche_usd:,.2f}")
                    c2.metric("Total USD", f"${total_usd:,.2f}")
                    c3.metric("Total MXN", f"${total_mxn:,.2f}")

                    # --- 6. GENERACIÓN DE PDF MEJORADO ---
                    pdf = FPDF()
                    pdf.add_page()
                    
                    # Logo (Grande pero equilibrado en la esquina superior izquierda)
                    try:
                        resp = requests.get(LOGO_URL, timeout=5)
                        # W=60 es un tamaño "grande" pero elegante para PDF
                        pdf.image(BytesIO(resp.content), 10, 10, 60)
                    except:
                        pdf.set_font("Arial", 'B', 14)
                        pdf.cell(0, 10, "CASA DORADA LOS CABOS", ln=True)

                    pdf.ln(35) # Espacio para que el logo no se encime
                    
                    # Título
                    pdf.set_font("Arial", 'B', 18)
                    pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                    pdf.ln(10)
                    
                    # Bloque de Información
                    pdf.set_fill_color(245, 245, 245)
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(0, 8, " RESERVATION DETAILS", ln=True, fill=True)
                    
                    pdf.set_font("Arial", '', 11)
                    pdf.cell(95, 10, f"Guest Name: {cliente.upper()}", border='B')
                    pdf.cell(95, 10, f"Confirmation #: {n_reserva}", border='B', ln=True)
                    
                    # Mejora en visualización de Fechas
                    f_in = check_in.strftime('%A, %d %b %Y')
                    f_out = check_out.strftime('%A, %d %b %Y')
                    pdf.cell(0, 10, f"Stay: {f_in} - to - {f_out} ({noches} Nights)", border='B', ln=True)
                    
                    pdf.ln(5)
                    pdf.set_font("Arial", 'B', 11)
                    pdf.cell(0, 8, " UPGRADE DETAILS", ln=True, fill=True)
                    
                    # Mejora en visualización de Categorías (Estilo Flecha)
                    pdf.set_font("Arial", '', 11)
                    pdf.ln(2)
                    pdf.cell(0, 10, "Original Category:", ln=True)
                    pdf.set_font("Arial", 'I', 12)
                    pdf.cell(0, 8, f"      {cat_orig}", ln=True)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 8, "      V", ln=True) # Una flecha visual simple
                    pdf.set_font("Arial", 'B', 13)
                    pdf.cell(0, 10, f"      {cat_dest} (NEW)", ln=True)
                    
                    # Resumen de Pago
                    pdf.ln(10)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, "PAYMENT SUMMARY", ln=True)
                    pdf.set_font("Arial", '', 12)
                    pdf.cell(100, 10, "Total Amount to be Paid:")
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(90, 10, f"USD ${total_usd:,.2f} / MXN ${total_mxn:,.2f}*", align='R', ln=True)
                    
                    pdf.set_font("Arial", 'I', 8)
                    pdf.cell(0, 5, f"*Exchange Rate: 1 USD = {tc_actual} MXN", align='R', ln=True)
                    
                    # Políticas y Firmas
                    pdf.ln(15)
                    pdf.set_font("Arial", 'B', 10); pdf.set_text_color(180, 0, 0)
                    pdf.cell(0, 5, "IMPORTANT: Non-refundable upgrade / Upgrade no reembolsable.", ln=True)
                    
                    pdf.ln(25)
                    curr_y = pdf.get_y()
                    pdf.line(10, curr_y, 90, curr_y)
                    pdf.line(110, curr_y, 190, curr_y)
                    pdf.set_font("Arial", '', 10); pdf.set_text_color(0, 0, 0)
                    pdf.cell(80, 10, "Guest Signature", align='C')
                    pdf.set_x(110)
                    pdf.cell(80, 10, "Hotel Representative", align='C')

                    # Botón de descarga
                    pdf_bytes = pdf.output(dest='S').encode('latin-1', errors='replace')
                    st.download_button(
                        label="📥 Descargar Acuerdo PDF",
                        data=pdf_bytes,
                        file_name=f"Upgrade_{n_reserva}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
