import streamlit as st
from fpdf import FPDF
from datetime import datetime
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 1. CARGAR CONFIGURACIÓN (DESCUENTO Y TC) ---
# Leemos la pestaña "Config" para que todos vean lo mismo
try:
    df_config = conn.read(worksheet="Config")
    # Asumimos que en la hoja 'Config' tienes una columna 'parametro' y otra 'valor'
    desc_actual = float(df_config.loc[df_config['parametro'] == 'descuento', 'valor'].values[0])
    tc_actual = float(df_config.loc[df_config['parametro'] == 'tc', 'valor'].values[0])
except:
    # Valores de respaldo si falla la conexión o no existe la hoja
    desc_actual = 55.0
    tc_actual = 18.0

# --- 2. CARGAR TARIFAS DEL DÍA ---
try:
    df_tarifas = conn.read(worksheet="Tarifas") # Tu hoja con 'Stay Date' y 'Current Rate'
except:
    df_tarifas = pd.DataFrame()

# --- DIFERENCIALES DUETTO (USD) ---
diferenciales_usd = {
    "Standard Two Double Beds": 0.0,
    "Junior Suite": 75.0,
    "Deluxe Suite": 0.0,
    "Executive Suite": 150.0,
    "One Bedroom Suite Garden": 225.0,
    "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0,
    "2 Bedroom Suite": 780.0,
    "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0,
    "Penthouse 3PH": 2625.0
}

# --- BARRA LATERAL (REVENUE MANAGER) ---
with st.sidebar:
    st.header("⚙️ Estrategia de Revenue")
    password = st.text_input("Contraseña Admin", type="password")
    
    if password == "Revenue2026":
        st.success("Acceso Autorizado")
        nuevo_desc = st.slider("Ajustar Descuento Web (%)", 0, 90, int(desc_actual))
        nuevo_tc = st.number_input("Tipo de Cambio (MXN)", value=tc_actual)
        
        if st.button("Actualizar para todo el Hotel"):
            # Aquí creamos el DataFrame para guardar en Drive
            nueva_config = pd.DataFrame([
                {"parametro": "descuento", "valor": nuevo_desc},
                {"parametro": "tc", "valor": nuevo_tc}
            ])
            # GUARDAR EN DRIVE (Sobreescribe la pestaña Config)
            conn.update(worksheet="Config", data=nueva_config)
            st.cache_data.clear() # Limpia caché para que todos vean el cambio
            st.rerun()
    else:
        st.info(f"Estrategia actual: {desc_actual}% Desc | TC: {tc_actual}")

# --- INTERFAZ DEL RECEPCIONISTA ---
st.title("🏨 Cotizador de Upsells")

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Nombre del Huésped")
    n_reserva = st.text_input("Número de Reserva")
    cat_orig = st.selectbox("Categoría Reservada", list(diferenciales_usd.keys()))
    fecha_estancia = st.date_input("Fecha de Estancia", datetime.now())

with col2:
    habitacion = st.text_input("Habitación")
    noches = st.number_input("Noches", min_value=1, value=1)
    cat_dest = st.selectbox("Categoría Upgrade", list(diferenciales_usd.keys()), index=1)

# --- LÓGICA DE CÁLCULO ---
# 1. Buscar Tarifa Base en la hoja "Tarifas"
tarifa_base_dia = 0
if not df_tarifas.empty:
    df_tarifas['Stay Date'] = pd.to_datetime(df_tarifas['Stay Date'])
    res = df_tarifas[df_tarifas['Stay Date'] == pd.to_datetime(fecha_estancia)]
    if not res.empty:
        tarifa_base_dia = res.iloc[0]['Current Rate']

# 2. Calcular Diferencia de Upgrade
diff_usd = diferenciales_usd[cat_dest] - diferenciales_usd[cat_orig]

if diff_usd > 0:
    # Cálculo final: (Diff * Factor Descuento de Drive) * TC de Drive * Impuestos
    factor = 1 - (desc_actual / 100)
    precio_noche_mxn = (diff_usd * factor) * tc_actual * 1.19
    total_estancia = precio_noche_mxn * noches

    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Adicional por Noche", f"${precio_noche_mxn:,.2f} MXN")
    c2.metric("Total Estancia", f"${total_estancia:,.2f} MXN")

    # --- GENERAR PDF (Misma lógica con las dos firmas) ---
    # ... (Aquí el código del PDF que ya tienes) ...
    
elif diff_usd < 0:
    st.error("⚠️ NO SE PERMITEN DOWNGRADES.")
else:
    st.warning("Selecciona una categoría superior.")
