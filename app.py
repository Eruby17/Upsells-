import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta, date
import pandas as pd
import requests
import io
import os

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Cotizador de upsells - Casa Dorada", page_icon="🏨", layout="wide")

# --- 2. IDENTIFICADORES Y URLS ---
SHEET_ID = "19hFs0Jgt58uWC_UXJ8_4aVCJVtX7fTBcHO7-iAVo1K0"
GID_CONFIG = "481323566"
GID_TARIFAS = "481323566"
LOGO_URL = "https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e"

@st.cache_data(ttl=600, show_spinner=False)
def obtener_datos_remotos():
    try:
        url_c = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID_CONFIG}"
        url_t = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID_TARIFAS}"
        
        headers = {"User-Agent": "Mozilla/5.0"}
        res_c = requests.get(url_c, headers=headers, timeout=7)
        res_t = requests.get(url_t, headers=headers, timeout=7)
        
        if res_c.status_code == 200 and res_t.status_code == 200:
            contenido_c = res_c.content.decode('utf-8')
            sep_c = ';' if ';' in contenido_c.split('\n')[0] else ','
            df_c = pd.read_csv(io.StringIO(contenido_c), sep=sep_c)
            
            contenido_t = res_t.content.decode('utf-8')
            sep_t = ';' if ';' in contenido_t.split('\n')[0] else ','
            df_t = pd.read_csv(io.StringIO(contenido_t), sep=sep_t)
            
            return df_c, df_t
        else:
            return None, None
    except Exception:
        return None, None

def procesar_informacion():
    df_1, df_2 = obtener_datos_remotos()
    tc_base = 17.40 
    desc_base = 62.0
    df_tarifas_limpias = pd.DataFrame()
    
    st.session_state['status_tarifas'] = "error" if df_2 is None else "ok"

    # --- PROCESAR PESTAÑA CONFIGURACIÓN ---
    if df_1 is not None:
        try:
            df_1.columns = [str(c).strip().lower() for c in df_1.columns]
            df_1['parametro'] = df_1['parametro'].astype(str).str.strip().str.lower()
            
            fila_desc = df_1[df_1['parametro'] == 'descuento']
            fila_tc = df_1[df_1['parametro'] == 'tc']
            
            if not fila_desc.empty:
                d_val = str(fila_desc['valor'].values[0]).replace('%', '').replace(',', '.').strip()
                desc_base = float(d_val)
                
            if not fila_tc.empty:
                t_val = str(fila_tc['valor'].values[0]).replace(',', '.').strip()
                tc_base = float(t_val)
        except Exception:
            pass

    # --- PROCESAR PESTAÑA TARIFAS (CRUCIAL PARA TEMPORADAS) ---
    if df_2 is not None:
        try:
            df_2.columns = [str(c).strip().lower() for c in df_2.columns]
            
            # Buscador flexible de columnas en la hoja de tarifas
            col_fecha = [c for c in df_2.columns if 'date' in c or 'fecha' in c]
            col_tarifa = [c for c in df_2.columns if 'rate' in c or 'tarifa' in c or 'precio' in c]
            col_cat = [c for c in df_2.columns if 'category' in c or 'categoria' in c or 'hab' in c]
            
            if col_fecha and col_tarifa and col_cat:
                c_f, c_t, c_c = col_fecha[0], col_tarifa[0], col_cat[0]
                
                # Conversión estricta de fechas al formato correcto de Python
                df_2['fecha_limpia'] = pd.to_datetime(df_2[c_f], errors='coerce', dayfirst=True).dt.date
                
                # Limpieza de caracteres de moneda, espacios y comas decimales regionales
                precios_limpios = df_2[c_t].astype(str).str.replace(' ', '').str.replace('$', '').str.replace('.', '', r=1).str.replace(',', '.')
                df_2['tarifa_num'] = pd.to_numeric(precios_limpios, errors='coerce')
                df_2['categoria_limpia'] = df_2[c_c].astype(str).str.strip()
                
                # Filtramos y nos quedamos con los registros completamente válidos
                df_tarifas_limpias = df_2.dropna(subset=['fecha_limpia', 'tarifa_num']).copy()
                
                if df_tarifas_limpias.empty:
                    st.session_state['status_tarifas'] = "error"
            else:
                st.session_state['status_tarifas'] = "error"
        except Exception:
            st.session_state['status_tarifas'] = "error"
        
    return desc_base, tc_base, df_tarifas_limpias

# Ejecución inicial de lectura
try:
    desc_actual, tc_desde_drive, df_tarifas = procesar_informacion()
except Exception:
    desc_actual = 62.0
    tc_desde_drive = 17.40
    df_tarifas = pd.DataFrame()
    st.session_state['status_tarifas'] = "error"

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
    if st.button("🔄 Sincronizar Datos", use_container_width=True):
        st.cache_data.clear()
        
    status = st.session_state.get('status_tarifas', 'error')
    if status == "ok":
        st.success("Tarifas cargadas correctamente")
    else:
        st.error("Problema al cargar tarifas")

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

# Listado de diferencias fijas de respaldo (Fallback de emergencia)
diferenciales_respaldo = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "1 Bedroom Ocean Front": 475.0, "2 Bedroom Suite": 780.0,
    "2 Bedroom Ocean Front": 980.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

col_cat1, col_cat2 = st.columns(2)
with col_cat1: cat_orig = st.selectbox("Categoría Original", list(diferenciales_respaldo.keys()))
with col_cat2: cat_dest = st.selectbox("Upgrade a Categoría", list(diferenciales_respaldo.keys()), index=1)

st.divider()

# --- 5. INICIALIZACIÓN DE SESIÓN ---
if "calc_ok" not in st.session_state:
    st.session_state.calc_ok = False
    st.session_state.pdf_data = None
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
        with st.spinner("Generando cotización por temporada..."):
            total_gap_estancia = 0.0
            usando_precios_dinamicos = True
            
            # Calculamos el gap noche por noche basándonos en el calendario del Drive
            for n in range(noches):
                fecha_noche = check_in + timedelta(days=n)
                
                if not df_tarifas.empty:
                    # Buscamos la tarifa de la habitación original para este día específico
                    t_orig_fila = df_tarifas[(df_tarifas['fecha_limpia'] == fecha_noche) & (df_tarifas['categoria_limpia'] == cat_orig)]
                    # Buscamos la tarifa de la habitación destino para este día específico
                    t_dest_fila = df_tarifas[(df_tarifas['fecha_limpia'] == fecha_noche) & (df_tarifas['categoria_limpia'] == cat_dest)]
                    
                    if not t_orig_fila.empty and not t_dest_fila.empty:
                        tarifa_o = t_orig_fila['tarifa_num'].values[0]
                        tarifa_d = t_dest_fila['tarifa_num'].values[0]
                        total_gap_estancia += (tarifa_d - tarifa_o)
                    else:
                        usando_precios_dinamicos = False
                else:
                    usando_precios_dinamicos = False
            
            # --- LÓGICA DE CONTROL Y PLAN DE RESPALDO (FALLBACK) ---
            if usando_precios_dinamicos and total_gap_estancia > 0:
                # El costo por noche promedio varía según la temporada real del Drive
                st.session_state.p_noche = (total_gap_estancia / noches) * (1 - desc_actual/100) * 1.30
            else:
                # Si las fechas no se cruzan o el Drive falló, usamos el diferencial plano de respaldo
                st.warning("⚠️ Nota: Fechas de tarifas no localizadas en Drive para esta combinación. Se aplicó tarifa base de respaldo.")
                gap_respaldo = diferenciales_respaldo.get(cat_dest, 0.0) - diferenciales_respaldo.get(cat_orig, 0.0)
                st.session_state.p_noche = (gap_respaldo * (1 - desc_actual/100)) * 1.30
                
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

                pdf_output_raw = pdf.output(dest='S')
                if isinstance(pdf_output_raw, bytes):
                    st.session_state.pdf_data = pdf_output_raw
                else:
                    st.session_state.pdf_data = bytes(pdf_output_raw, 'latin-1')

                st.session_state.calc_ok = True
                
                if os.path.exists(logo_path):
                    os.remove(logo_path)
                    
            except Exception as pdf_err:
                st.error(f"Error crítico al compilar el PDF de cotización: {str(pdf_err)}")
                st.session_state.calc_ok = False

# --- 6. MUESTRA DE RESULTADOS Y DESCARGA ---
if st.session_state.calc_ok and st.session_state.pdf_data is not None:
    res1, res2, res3, res4 = st.columns(4)
    res1.metric("Noches", f"{st.session_state.n_noches}")
    res2.metric("USD / Noche", f"${st.session_state.p_noche:,.2f}")
    res3.metric("Total USD", f"${st.session_state.t_usd:,.2f}")
    res4.metric("Total MXN", f"${st.session_state.t_mxn:,.2f}")

    st.download_button(
        label="📥 Descargar PDF de Upgrade", 
        data=st.session_state.pdf_data, 
        file_name=f"Upsell_{st.session_state.c_reserva}.pdf", 
        mime="application/pdf", 
        use_container_width=True
    )
