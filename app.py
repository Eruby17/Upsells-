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
LOGO_URL = "https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e"

def get_csv_url(gid):
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"

# --- 3. SISTEMA DE CACHÉ PERSISTENTE ---
@st.cache_data(ttl=600)  # Los datos se guardan en memoria por 10 minutos
def obtener_datos_remotos():
    try:
        df_c = pd.read_csv(get_csv_url(GID_CONFIG))
        df_t = pd.read_csv(get_csv_url(GID_TARIFAS))
        return df_c, df_t
    except Exception as e:
        st.error(f"Error de conexión con la base de datos: {e}")
        return None, None

# --- 4. PROCESAMIENTO DE DATOS ---
def procesar_informacion():
    df_1, df_2 = obtener_datos_remotos()
    
    # Valores por defecto
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
            # Limpieza de Rate (solo números)
            df_2['Rate_Num'] = pd.to_numeric(df_2['Rate'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            df_tarifas_limpias = df_2.dropna(subset=['Fecha_Final', 'Rate_Num']).copy()
        except: pass
        
    return desc_actual, tc_actual, df_tarifas_limpias

# Carga inicial de datos procesados
desc_actual, tc_actual, df_tarifas = procesar_informacion()

# --- 5. INTERFAZ DE USUARIO ---
st.title("🏨 Cotizador de Upsells")

with st.sidebar:
    st.image(LOGO_URL, width=150)
    st.subheader("Configuración Actual")
    st.metric("Descuento Web", f"{desc_actual}%")
    st.metric("T.C. Manual", f"${tc_actual} MXN")
    if st.button("🔄 Actualizar Base de Datos"):
        st.cache_data.clear()
        st.rerun()

diferenciales = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

# Formulario de entrada
col_nom, col_fol = st.columns(2)
with col_nom: cliente = st.text_input("Nombre del Huésped", placeholder="Ej. Juan Pérez")
with col_fol: n_reserva = st.text_input("Número de Confirmación", placeholder="Ej. 123456")

col_in, col_out = st.columns(2)
with col_in: check_in = st.date_input("Fecha de Check-in", datetime.now().date())
with col_out: check_out = st.date_input("Fecha de Check-out", datetime.now().date() + timedelta(days=1))

col_cat1, col_cat2 = st.columns(2)
with col_cat1: cat_orig = st.selectbox("Categoría Reservada", list(diferenciales.keys()))
with col_cat2: cat_dest = st.selectbox("Categoría de Upgrade", list(diferenciales.keys()), index=1)

# --- 6. BOTÓN DE ACCIÓN (EVITA CRASHES) ---
st.divider()
if st.button("💰 Calcular Cotización", type="primary", use_container_width=True):
    
    with st.spinner("Buscando tarifas y calculando impuestos..."):
        noches = (check_out - check_in).days
        
        if noches <= 0:
            st.error("Error: La fecha de salida debe ser posterior a la de entrada.")
        elif df_tarifas.empty:
            st.error("Error: No se pudo cargar la tabla de tarifas.")
        else:
            # Búsqueda de tarifa base
            filtro = df_tarifas[df_tarifas['Fecha_Final'] <= check_in].sort_values('Fecha_Final', ascending=False)
            
            if filtro.empty:
                st.warning(f"No se encontró tarifa exacta para {check_in}. Se requiere revisión manual.")
            else:
                tarifa_base = float(filtro.iloc[0]['Rate_Num'])
                # Lógica de cálculo
                gap = diferenciales[cat_dest] - diferenciales[cat_orig]
                
                if gap <= 0:
                    st.warning("Selecciona una categoría superior a la original.")
                else:
                    # Fórmula solicitada: (Gap con descuento) + 30% impuestos
                    precio_noche_usd = (gap * (1 - desc_actual/100)) * 1.30
                    total_usd = precio_noche_usd * noches
                    total_mxn = total_usd * tc_actual

                    # Resultados Visuales
                    st.success("Cotización generada exitosamente")
                    res1, res2, res3 = st.columns(3)
                    res1.metric("USD / Noche (Inc. Tax)", f"${precio_noche_usd:,.2f}")
                    res2.metric("Total USD", f"${total_usd:,.2f}")
                    res3.metric("Total MXN", f"${total_mxn:,.2f}")

                    # --- 7. GENERACIÓN DE PDF ---
                    pdf = FPDF()
                    pdf.add_page()
                    
                    # Logo con manejo de error
                    try:
                        resp = requests.get(LOGO_URL, timeout=5)
                        pdf.image(BytesIO(resp.content), 10, 8, 45)
                    except:
                        pdf.set_font("Arial", 'B', 12); pdf.cell(0, 10, "CASA DORADA LOS CABOS", ln=True)

                    pdf.ln(25)
                    pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                    
                    pdf.set_font("Arial", '', 10)
                    pdf.ln(10)
                    pdf.cell(0, 8, f"Guest: {cliente.upper()}", border='B', ln=True)
                    pdf.cell(0, 8, f"Confirmation: {n_reserva}", border='B', ln=True)
                    pdf.cell(0, 8, f"Dates: {check_in} to {check_out} ({noches} nights)", border='B', ln=True)
                    pdf.cell(0, 8, f"Upgrade: {cat_orig} -> {cat_dest}", border='B', ln=True)
                    
                    pdf.ln(10)
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(0, 10, f"TOTAL AMOUNT DUE: USD ${total_usd:,.2f} / MXN ${total_mxn:,.2f}", ln=True)
                    pdf.set_font("Arial", 'I', 8)
                    pdf.cell(0, 5, f"*Exchange rate: 1 USD = {tc_actual} MXN", ln=True)

                    pdf.ln(20)
                    pdf.set_font("Arial", '', 9)
                    pdf.multi_cell(0, 5, "Este upgrade es NO REEMBOLSABLE. / This upgrade is NON-REFUNDABLE.")
                    
                    # Salida de PDF
                    try:
                        pdf_bytes = pdf.output(dest='S').encode('latin-1', errors='replace')
                        st.download_button(
                            label="📥 Descargar Acuerdo PDF",
                            data=pdf_bytes,
                            file_name=f"Upgrade_{n_reserva}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                    except Exception as e:
                        st.error(f"Error al generar el archivo PDF: {e}")
