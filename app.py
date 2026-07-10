import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
import requests
import os

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Cotizador de upsells - Casa Dorada", page_icon="🏨", layout="wide")

# --- 2. IDENTIFICADORES Y URLS ---
SHEET_ID = "19hFs0Jgt58uWC_UXJ8_4aVCJVtX7fTBcHO7-iAVo1K0"
GID_CONFIG = "481323566"
GID_TARIFAS = "0"
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
    tc_base = 17.40 
    desc_base = 62.0
    df_tarifas_limpias = pd.DataFrame()

    if df_1 is not None:
        try:
            df_1.columns = [str(c).strip().lower() for c in df_1.columns]
            d_val = df_1[df_1['parametro'].str.contains('descuento', na=False)]['valor'].values[0]
            t_val = df_1[df_1['parametro'].str.contains('tc', na=False)]['valor'].values[0]
            desc_base = float(str(d_val).replace(',', '.'))
            tc_base = float(str(t_val).replace(',', '.'))
        except: pass

    if df_2 is not None:
        try:
            df_2.columns = [str(c).strip() for c in df_2.columns]
            df_2['Fecha_Final'] = pd.to_datetime(df_2['Date'], errors='coerce', dayfirst=True).dt.date
            df_2['Rate_Num'] = pd.to_numeric(df_2['Rate'].astype(str).str.replace(r'[^\d.]', '', regex=True), errors='coerce')
            df_tarifas_limpias = df_2.dropna(subset=['Fecha_Final', 'Rate_Num']).copy()
        except: pass
        
    return desc_base, tc_base, df_tarifas_limpias

desc_actual, tc_desde_drive, df_tarifas = procesar_informacion()

# --- 3. PANEL LATERAL (SIDEBAR) ---
with st.sidebar:
    st.image(LOGO_URL, use_container_width=True)
    st.header("Configuración")
    st.metric("Descuento Aplicado", f"{desc_actual}%")
    
    tc_actual = st.number_input(
        "Tipo de Cambio (MXN)",
        min_value=1.0,
        value=float(tc_desde_drive),
        step=0.1,
        format="%.2f"
    )
    
    st.divider()
    if st.button("🔄 Sincronizar Datos"):
        st.cache_data.clear()
        st.rerun()

# --- 4. INTERFAZ PRINCIPAL ---
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
    "1 Bedroom Suite Plus": 375.0, "1 Bedroom Ocean Front": 475.0, "2 Bedroom Suite": 780.0,
    "2 Bedroom Ocean Front": 980.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

col_cat1, col_cat2 = st.columns(2)
with col_cat1: cat_orig = st.selectbox("Categoría Original", list(diferenciales.keys()))
with col_cat2: cat_dest = st.selectbox("Upgrade a Categoría", list(diferenciales.keys()), index=1)

# --- NUEVA SECCIÓN DE PRECIOS Y AJUSTES ---
st.subheader("Ajuste de Tarifa Comercial")
gap = diferenciales[cat_dest] - diferenciales[cat_orig]
precio_minimo_calculado = (gap * (1 - desc_actual/100)) * 1.30

col_tipo_precio, col_precio_final = st.columns(2)

with col_tipo_precio:
    tipo_precio = st.radio(
        "Estrategia de Venta",
        ["Aplicar Mínimo Sugerido", "Ingresar Precio Manual (Vender más caro)"],
        horizontal=True
    )

with col_precio_final:
    if tipo_precio == "Ingresar Precio Manual (Vender más caro)":
        precio_venda_usd = st.number_input(
            "Precio por Noche Final (USD)",
            min_value=float(precio_minimo_calculado),
            value=float(precio_minimo_calculado),
            step=5.0,
            format="%.2f",
            help=f"No puede ser menor al precio mínimo calculado con descuento (${precio_minimo_calculado:,.2f} USD)"
        )
    else:
        precio_venda_usd = precio_minimo_calculado
        st.metric("Precio por Noche Fijado (USD)", f"${precio_venda_usd:,.2f}")

st.divider()

# --- 5. CÁLCULOS Y PDF ---
if "calculado" not in st.session_state:
    st.session_state.calculado = False
    st.session_state.pdf_output = None
    st.session_state.precio_noche_usd = 0.0
    st.session_state.total_usd = 0.0
    st.session_state.total_mxn = 0.0
    st.session_state.noches_guardadas = 0
    st.session_state.reserva_guardada = ""

if st.button("💰 Calcular Cotización", type="primary", use_container_width=True):
    if noches <= 0:
        st.error("La fecha de salida debe ser posterior a la de entrada.")
        st.session_state.calculado = False
    else:
        with st.spinner("Generando documento..."):
            # Fijamos los cálculos en base al precio seleccionado (Mínimo o Manual)
            st.session_state.precio_noche_usd = precio_venda_usd
            st.session_state.total_usd = precio_venda_usd * noches
            st.session_state.total_mxn = st.session_state.total_usd * tc_actual
            st.session_state.noches_guardadas = noches
            st.session_state.reserva_guardada = n_reserva if n_reserva else "Sin_Numero"

            # --- GENERACIÓN DE PDF ---
            pdf = FPDF()
            pdf.add_page()
            
            logo_path = "temp_logo.png"
            try:
                r = requests.get(LOGO_URL, timeout=10)
                if r.status_code == 200:
                    with open(logo_path, "wb") as f:
                        f.write(r.content)
                    pdf.image(logo_path, 10, 10, 50) 
            except:
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
            pdf.cell(95, 8, f"Guest: {cliente.upper()}".encode('latin-1', 'replace').decode('latin-1'))
            pdf.cell(95, 8, f"Confirmation: {n_reserva}".encode('latin-1', 'replace').decode('latin-1'), ln=True)
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

            # Desglose de Costos (Solo muestra el nuevo precio acordado)
            pdf.set_font("Arial", '', 11)
            pdf.cell(120, 10, f"Upgrade Fee per Night ({noches} nights):")
            pdf.cell(70, 10, f"USD ${st.session_state.precio_noche_usd:,.2f}", align='R', ln=True)
            
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(120, 10, "Total Upgrade Fee (Including Taxes):", border='T')
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(70, 10, f"USD ${st.session_state.total_usd:,.2f}", border='T', align='R', ln=True)
            
            pdf.set_font("Arial", 'I', 10)
            pdf.cell(120, 8, f"Exchange Rate / Tipo de Cambio (1 USD = {tc_actual} MXN):")
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(70, 8, f"MXN ${st.session_state.total_mxn:,.2f}", align='R', ln=True)
            
            pdf.ln(15)
            pdf.set_font("Arial", 'I', 9)
            
            # Texto limpio sin caracteres especiales conflictivos para FPDF estándar
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

            # Extracción limpia y segura a memoria binaria
            st.session_state.pdf_output = bytes(pdf.output(dest='S'))

            if os.path.exists(logo_path): os.remove(logo_path)
            st.session_state.calculado = True

# Muestra los resultados y habilita la descarga
if st.session_state.calculado:
    res1, res2, res3, res4 = st.columns(4)
    res1.metric("Noches", f"{st.session_state.noches_guardadas}")
    res2.metric("USD / Noche (Final)", f"${st.session_state.precio_noche_usd:,.2f}")
    res3.metric("Total USD", f"${st.session_state.total_usd:,.2f}")
    res4.metric("Total MXN", f"${st.session_state.total_mxn:,.2f}")

    st.download_button(
        "📥 Descargar PDF", 
        data=st.session_state.pdf_output, 
        file_name=f"Upsell_{st.session_state.reserva_guardada}.pdf", 
        mime="application/pdf", 
        use_container_width=True
    )
