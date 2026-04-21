import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- 2. CONFIGURACIÓN DE IDENTIFICADORES (SEGÚN TUS DATOS) ---
SHEET_ID = "19hFs0Jgt58uWC_UXJ8_4aVCJVtX7fTBcHO7-iAVo1K0"
GID_CONFIG = "481323566"  # Pestaña 1
GID_TARIFAS = "0"          # Pestaña 2

def get_csv_url(gid):
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"

# --- 3. CARGA DE DATOS ---
@st.cache_data(ttl=0)
def cargar_datos_directos():
    try:
        # Cargamos Configuración
        df_c = pd.read_csv(get_csv_url(GID_CONFIG))
        # Cargamos Tarifario
        df_t = pd.read_csv(get_csv_url(GID_TARIFAS))
        return df_c, df_t
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None, None

df_1, df_2 = cargar_datos_directos()

# --- 4. PROCESAMIENTO DE VALORES (SIDEBAR) ---
desc_actual, tc_actual = 62.0, 17.40 # Valores de respaldo

if df_1 is not None:
    try:
        df_1.columns = [str(c).strip().lower() for c in df_1.columns]
        # Extraer Descuento y Tipo de Cambio
        d_val = df_1[df_1['parametro'].str.contains('descuento', case=False, na=False)]['valor'].values[0]
        t_val = df_1[df_1['parametro'].str.contains('tc', case=False, na=False)]['valor'].values[0]
        desc_actual = float(str(d_val).replace(',', '.'))
        tc_actual = float(str(t_val).replace(',', '.'))
    except:
        pass

# Procesar Tarifario
df_tarifas = pd.DataFrame()
if df_2 is not None:
    try:
        df_2.columns = [str(c).strip() for c in df_2.columns]
        # Convertir fecha del Excel (21/04/2026) a formato de comparación
        df_2['Fecha_ID'] = pd.to_datetime(df_2['Date'], dayfirst=True, errors='coerce').dt.date
        # Limpiar tarifa
        df_2['Rate_Num'] = pd.to_numeric(df_2['Rate'].astype(str).str.replace(',', '.'), errors='coerce')
        df_tarifas = df_2.dropna(subset=['Fecha_ID', 'Rate_Num'])
    except:
        pass

# --- 5. INTERFAZ ---
st.title("🏨 Professional Upsell Generator")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.metric("Descuento", f"{desc_actual}%")
    st.metric("Tipo de Cambio", f"${tc_actual} MXN")
    if st.button("🔄 Sincronizar Datos"):
        st.cache_data.clear()
        st.rerun()

# --- FORMULARIO ---
diferenciales = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

cliente = st.text_input("Nombre del Huésped")
c1, c2 = st.columns(2)
with c1:
    cat_orig = st.selectbox("Categoría Original", list(diferenciales.keys()))
    fecha_sel = st.date_input("Fecha de Entrada", datetime.now().date())
with c2:
    n_reserva = st.text_input("Número de Confirmación")
    cat_dest = st.selectbox("Upgrade a", list(diferenciales.keys()), index=3)

# --- 6. CÁLCULOS ---
if not df_tarifas.empty:
    # Buscar la tarifa base del día
    match = df_tarifas[df_tarifas['Fecha_ID'] == fecha_sel]
    
    if not match.empty:
        tarifa_base = float(match.iloc[0]['Rate_Num'])
        
        # Lógica de Diferencia: (Base + Upg) - (Base + Orig)
        monto_orig = tarifa_base + diferenciales[cat_orig]
        monto_upg = tarifa_base + diferenciales[cat_dest]
        gap = monto_upg - monto_orig
        
        if gap > 0:
            # Cálculo final: Gap -> Descuento -> Impuestos (30%)
            usd_con_desc = gap * (1 - desc_actual/100)
            total_usd = usd_con_desc * 1.30
            total_mxn = total_usd * tc_actual
            
            st.divider()
            st.success(f"Tarifa base encontrada: ${tarifa_base} USD")
            col_a, col_b = st.columns(2)
            col_a.metric("Total USD (c/ Impuestos)", f"${total_usd:,.2f}")
            col_b.metric("Total MXN (c/ Impuestos)", f"${total_mxn:,.2f}")
            
            if st.button("📝 Generar Acuerdo PDF"):
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                pdf.ln(10); pdf.set_font("Arial", size=11)
                pdf.cell(0, 8, f"Huésped: {cliente.upper()}", ln=True)
                pdf.cell(0, 8, f"Confirmación: {n_reserva}", ln=True)
                pdf.cell(0, 8, f"Fecha: {fecha_sel.strftime('%d/%m/%Y')}", ln=True)
                pdf.cell(0, 8, f"Mejora: {cat_orig} -> {cat_dest}", ln=True)
                pdf.ln(5); pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, f"TOTAL A PAGAR: USD ${total_usd:,.2f} / MXN ${total_mxn:,.2f}", ln=True)
                
                st.download_button("📥 Descargar PDF", pdf.output(dest='S').encode('latin-1'), f"Upsell_{n_reserva}.pdf")
        else:
            st.warning("La categoría de destino debe ser superior a la original.")
    else:
        st.error(f"No hay tarifa cargada en el Excel para el día {fecha_sel.strftime('%d/%m/%Y')}")
else:
    st.info("Sincronizando con el tarifario de Google Sheets...")
