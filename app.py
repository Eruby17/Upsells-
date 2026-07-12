import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
import requests
import io
import os

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Cotizador de upsells - Casa Dorada", page_icon="🏨", layout="wide")

# --- 2. IDENTIFICADORES Y URLS ---
SHEET_ID = "19hFs0Jgt58uWC_UXJ8_4aVCJVtX7fTBcHO7-iAVo1K0"
GID_CONFIG = "481323566"
LOGO_URL = "https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e"

@st.cache_data(ttl=600, show_spinner=False)
def obtener_datos_config():
    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID_CONFIG}"
        headers = {"User-Agent": "Mozilla/5.0"}
        respuesta = requests.get(url, headers=headers, timeout=7)
        
        if respuesta.status_code == 200:
            contenido = respuesta.content.decode('utf-8')
            separador = ';' if ';' in contenido.split('\n')[0] else ','
            df = pd.read_csv(io.StringIO(contenido), sep=separador)
            return df
        return None
    except Exception:
        return None

def procesar_config():
    df = obtener_datos_config()
    tc_base = 17.40
    desc_base = 62.0
    
    if df is not None:
        try:
            df.columns = [str(c).strip().lower() for c in df.columns]
            df['parametro'] = df['parametro'].astype(str).str.strip().str.lower()
            
            fila_desc = df[df['parametro'] == 'descuento']
            fila_tc = df[df['parametro'] == 'tc']
            
            if not fila_desc.empty:
                d_val = str(fila_desc['valor'].values[0]).replace('%', '').replace(',', '.').strip()
                desc_base = float(d_val)
                
            if not fila_tc.empty:
                t_val = str(fila_tc['valor'].values[0]).replace(',', '.').strip()
                tc_base = float(t_val)
        except Exception:
            pass
            
    return desc_base, tc_base

# Lectura de la configuración base
try:
    desc_actual, tc_desde_drive = procesar_config()
except Exception:
    desc_actual = 62.0
    tc_desde_drive = 17.40

# --- 3. PANEL LATERAL (SIDEBAR) ---
with st.sidebar:
    try:
        st.image(LOGO_URL, use_container_width=True)
    except Exception:
        st.subheader("Casa Dorada Los Cabos")
        
    st.header("Configuración")
    st.metric("Descuento Aplicado", f"{desc_actual}%")
    
    tc_actual = st.number_input(
        "Tipo de Cambio (MXN)",
        min_value=1.0,
        value=float(tc_desde_drive) if isinstance(tc_desde_drive, (int, float)) else 17.40,
        step=0.1,
        format="%.2f"
    )
    
    st.divider()
    if st.button("🔄 Sincronizar Drive", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# --- 4. INTERFAZ PRINCIPAL ---
st.title("🏨 Cotizador de upsells")

col_nom, col_fol = st.columns(2)
with col_nom: cliente = st.text_input("Nombre del Huésped", value="")
with col_fol: n_reserva = st.text_input("Número de Confirmación", value="")

col_in, col_out = st.columns(2)
with col_in: check_in = st.date_input("Check-in", datetime.now().date())
with col_out: check_out = st.date_input("Check-out", datetime.now().date() + timedelta(days=1))

if check_out and check_in:
    noches = (check_out - check_in).days
else:
    noches = 1

# Listado original de valores de referencia fijos por categoría
valores_habitaciones = {
    "Standard Two Double Beds": 0.0,
    "Junior Suite": 75.0,
    "Deluxe Suite": 0.0,
    "Executive Suite": 150.0,
    "One Bedroom Suite Garden": 225.0,
    "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0,
    "1 Bedroom Ocean Front": 475.0,
    "2 Bedroom Suite": 780.0,
    "2 Bedroom Ocean Front": 980.0,
    "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0,
    "Penthouse 3PH": 2625.0
}

col_cat1, col_cat2 = st.columns(2)
with col_cat1: cat_orig = st.selectbox("Categoría Original", list(valores_habitaciones.keys()))
with col_cat2: cat_dest = st.selectbox("Upgrade a Categoría", list(valores_habitaciones.keys()), index=1)

st.divider()

# --- 5. INICIALIZACIÓN DE SESIÓN ---
if "calc_ok" not in st.session_state:
    st.session_state.calc_ok = False
    st.session_state.pdf_bytes = None
    st.session_state.p_noche = 0.0
    st.session_state.t_usd = 0.0
    st.session_state.t_mxn = 0.0
    st.session_state.n_noches = 0
    st.session_state.c_reserva = ""

if st.button("💰 Calcular Cotización", type="primary", use_container_width=True):
    if noches <= 0:
        st.error("La fecha de salida debe ser posterior a la de entrada.")
        st.session_state.calc_ok = False
    else:
        # Matemática fija e inquebrantable original
        gap_fijo = valores_habitaciones.get(cat_dest, 0.0) - valores_habitaciones.get(cat_orig, 0.0)
        
        st.session_state.p_noche = (gap_fijo * (1 - desc_actual/100)) * 1.30
        st.session_state.t_usd = st.session_state.p_noche * noches
        st.session_state.t_mxn = st.session_state.t_usd * tc_actual
        st.session_state.n_noches = noches
        st.session_state.c_reserva = n_reserva if n_reserva.strip() else "Sin_Numero"

        try:
            # --- GENERACIÓN DE PDF ---
            pdf = FPDF()
            pdf.add_page()
            
            logo_path = "temp_logo.png"
            try:
                r = requests.get(LOGO_URL, timeout=5)
                if r.status_code == 200:
                    with open(logo_path, "wb") as f:
                        f.write(r.content)
                    pdf.image(logo_path, 10, 10, 50) 
            except Exception:
                pdf.set_font("Arial", 'B', 12)
                pdf.cell(0, 10, "CASA DORADA LOS CABOS", ln=True)

            pdf.ln(30)
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='R')
            pdf.set_font("Arial", '', 10)
            pdf.cell(0, 5, f"Date: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='R')
            pdf.ln(10)

            # Información del Huésped
            pdf.set_fill_color(30, 55, 110) 
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, "   GUEST INFORMATION", ln=True, fill=True)
            
            pdf.set_text_color(0, 0, 0)
            pdf.set_font("Arial", '', 11)
            pdf.ln(2)
            
            g_name = cliente.upper() if cliente else "VALUED GUEST"
            pdf.cell(95, 8, f"Guest: {g_name}".encode('latin-1', 'replace').decode('latin-1'))
            pdf.cell(95, 8, f"Confirmation: {st.session_state.c_reserva}".encode('latin-1', 'replace').decode('latin-1'), ln=True)
            pdf.cell(95, 8, f"Check-in: {check_in.strftime('%d %b, %Y')}")
            pdf.cell(95, 8, f"Check-out: {check_out.strftime('%d %b, %Y')}", ln=True)
            pdf.cell(95, 8, f"Number of Nights: {noches}", ln=True)
            pdf.ln(5)

            # Detalles del Upgrade
            pdf.set_text_color(255, 255, 255)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(0, 8, "   ROOM UPGRADE DETAILS", ln=True, fill=True)
            
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(60, 10, "   Original Room:", border='B', fill=True)
            pdf.set_font("Arial", '', 10)
            pdf.cell(130, 10, f"   {cat_orig}".encode('latin-1', 'replace').decode('latin-1'), border='B', ln=True)
            
            pdf.set_fill_color(230, 240, 255) 
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(60, 12, "   UPGRADED TO:", border='B', fill=True)
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(130, 12, f"   {cat_dest}".encode('latin-1', 'replace').decode('latin-1'), border='B', ln=True)
            pdf.ln(5)

            # Desglose de Costos final
            pdf.set_font("Arial", '', 11)
            pdf.cell(120, 10, f"Upgrade Fee per Night ({noches} nights):")
            pdf.cell(70, 10, f"USD ${st.session_state.p_noche:,.2f}", align='R', ln=True)
            
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(120, 10, "Total Upgrade Fee (Including Taxes):", border='T')
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(70, 10, f"USD ${st.session_state.t_usd:,.2f}", border='T', align='R', ln=True)
            
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(120, 8, f"Exchange Rate / Tipo de Cambio (1 USD = {tc_actual} MXN):")
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(70, 8, f"MXN ${st.session_state.t_mxn:,.2f}", align='R', ln=True)
            
            pdf.ln(15)
            pdf.set_font("Arial", 'I', 9)
            
            terminos_texto = (
                "Terms: This upgrade is non-refundable and applies for the entire stay. "
                "In the event of an early departure, no refund will be issued for the upsell.\n"
                "Este upgrade no es reembolsable y aplica por la estancia completa. "
                "En caso de salida anticipada, no aplicara ningun reembolso por el upsell."
            )
            pdf.multi_cell(0, 5, terminos_texto.encode('latin-1', 'replace').decode('latin-1'))
            
            pdf.ln(25)
            pdf.line(10, pdf.get_y(), 85, pdf.get_y())
            pdf.line(125, pdf.get_y(), 200, pdf.get_y())
            pdf.set_font("Arial", '', 10)
            pdf.cell(75, 10, "Guest Signature", align='C')
            pdf.set_x(125)
            pdf.cell(75, 10, "Front Office Representative", align='C')

            # MÉTODO CORREGIDO ANTI-CRASH: Forzamos la exportación segura mediante buffer de bytes nativos
            st.session_state.pdf_bytes = bytes(pdf.output(dest='S'), 'latin-1') if isinstance(pdf.output(dest='S'), str) else pdf.output(dest='S')
            st.session_state.calc_ok = True
            
            if os.path.exists(logo_path):
                os.remove(logo_path)
                
        except Exception as pdf_err:
            st.error(f"Error al generar el PDF: {str(pdf_err)}")
            st.session_state.calc_ok = False

# --- 6. MUESTRA DE RESULTADOS Y DESCARGA ---
if st.session_state.calc_ok and st.session_state.pdf_bytes is not None:
    res1, res2, res3, res4 = st.columns(4)
    res1.metric("Noches", f"{st.session_state.n_noches}")
    res2.metric("USD / Noche", f"${st.session_state.p_noche:,.2f}")
    res3.metric("Total USD", f"${st.session_state.t_usd:,.2f}")
    res4.metric("Total MXN", f"${st.session_state.t_mxn:,.2f}")

    st.download_button(
        label="📥 Descargar PDF de Upgrade", 
        data=st.session_state.pdf_bytes, 
        file_name=f"Upsell_{st.session_state.c_reserva}.pdf", 
        mime="application/pdf", 
        use_container_width=True
    )
