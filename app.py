import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- VALORES DE RESPALDO ---
desc_actual, tc_actual = 62.0, 17.40

# --- CARGA ROBUSTA POR ORDEN DE PESTAÑA ---
@st.cache_data(ttl=0)
def obtener_datos():
    try:
        # En lugar de usar nombres "1" o "2", leemos el spreadsheet completo
        # y accedemos por posición si el nombre falla.
        # Intentamos leer la primera pestaña (Config) y la segunda (Tarifas)
        df_c = conn.read(worksheet="1", ttl=0)
        df_t = conn.read(worksheet="2", ttl=0)
        return df_c, df_t
    except Exception as e:
        st.error(f"Error de conexión 400: Intentando método alternativo...")
        # Si falla por nombre, intentamos leer la primera hoja disponible
        try:
            return conn.read(ttl=0), None
        except:
            return None, None

df_1, df_2 = obtener_datos()

# --- PROCESAR CONFIG ---
if df_1 is not None and not df_1.empty:
    try:
        df_1.columns = [str(c).strip().lower() for c in df_1.columns]
        d_val = df_1[df_1['parametro'].str.contains('descuento', na=False)]['valor'].values[0]
        t_val = df_1[df_1['parametro'].str.contains('tc', na=False)]['valor'].values[0]
        desc_actual = float(str(d_val).replace(',', '.'))
        tc_actual = float(str(t_val).replace(',', '.'))
    except: pass

# --- PROCESAR TARIFAS ---
df_tarifas = pd.DataFrame()
if df_2 is not None and not df_2.empty:
    try:
        df_2.columns = [str(c).strip() for c in df_2.columns]
        df_2['Fecha_ID'] = pd.to_datetime(df_2['Date'], dayfirst=True, errors='coerce').dt.strftime('%Y-%m-%d')
        df_2['Rate_Num'] = pd.to_numeric(df_2['Rate'].astype(str).str.replace(',', '.'), errors='coerce')
        df_tarifas = df_2.dropna(subset=['Fecha_ID', 'Rate_Num'])
    except: pass

# --- INTERFAZ ---
st.title("🏨 Upsell Agreement Generator")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.metric("Descuento", f"{desc_actual}%")
    st.metric("T.C.", f"${tc_actual} MXN")
    if st.button("🔄 Sincronizar"):
        st.cache_data.clear()
        st.rerun()

# --- CÁLCULO ---
# (Diferenciales se mantienen igual)
diferenciales = {
    "Standard Two Double Beds": 0.0, "Junior Suite": 75.0, "Deluxe Suite": 0.0,
    "Executive Suite": 150.0, "One Bedroom Suite Garden": 225.0, "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0, "2 Bedroom Suite": 780.0, "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0, "Penthouse 3PH": 2625.0
}

cliente = st.text_input("Nombre del Huésped")
col1, col2 = st.columns(2)
with col1:
    cat_orig = st.selectbox("Categoría Original", list(diferenciales.keys()))
    fecha_sel = st.date_input("Fecha", datetime.now().date())
with col2:
    n_reserva = st.text_input("Confirmación #")
    cat_dest = st.selectbox("Upgrade a", list(diferenciales.keys()), index=3)

if not df_tarifas.empty:
    target = fecha_sel.strftime('%Y-%m-%d')
    match = df_tarifas[df_tarifas['Fecha_ID'] == target]
    if not match.empty:
        base = float(match.iloc[0]['Rate_Num'])
        diff = (base + diferenciales[cat_dest]) - (base + diferenciales[cat_orig])
        if diff > 0:
            res_usd = (diff * (1 - desc_actual/100)) * 1.30
            st.metric("Total USD", f"${res_usd:,.2f}")
            st.metric("Total MXN", f"${res_usd * tc_actual:,.2f}")
            if st.button("Generar PDF"):
                # (Código de PDF simplificado para prueba)
                st.write("PDF Generado (Listo para descargar)")
    else:
        st.warning(f"No se encontró tarifa para {fecha_sel}")
else:
    st.error("No se pudo cargar la tabla de tarifas. Revisa la pestaña '2'.")
