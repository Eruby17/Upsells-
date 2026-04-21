import streamlit as st
from fpdf import FPDF
from datetime import datetime
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARGAR CONFIGURACIÓN DESDE DRIVE ---
# ttl="0" para que siempre lea el dato más reciente sin caché
try:
    df_config = conn.read(worksheet="Config", ttl="0") 
    desc_actual = float(df_config.loc[df_config['parametro'] == 'descuento', 'valor'].values[0])
    tc_actual = float(df_config.loc[df_config['parametro'] == 'tc', 'valor'].values[0])
except Exception:
    # Valores de respaldo por si el Excel está vacío o mal configurado
    desc_actual = 55.0
    tc_actual = 18.0

# --- CARGAR TARIFAS BASE ---
try:
    df_tarifas = conn.read(worksheet="Tarifas", ttl="1h")
except Exception:
    df_tarifas = pd.DataFrame()

# --- DIFERENCIALES DUETTO (USD) ---
# Extraídos de tu captura de pantalla de Duetto
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

# --- BARRA LATERAL INFORMATIVA ---
with st.sidebar:
    st.header("📊 Estrategia de Venta")
    st.write("Valores controlados desde Google Drive")
    st.metric("Descuento Aplicado", f"{desc_actual}%")
    st.metric("Tipo de Cambio", f"${tc_actual} MXN")
    st.divider()
    st.caption("Revenue Manager: Para actualizar estos valores, modifique la pestaña 'Config' en su archivo de Google Sheets.")

# --- INTERFAZ DEL RECEPCIONISTA ---
st.title("🏨 Cotizador de Upsells")

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Nombre del Huésped", placeholder="Ej: Juan Pérez")
    n_reserva = st.text_input("Número de Reserva", placeholder="Confirmación")
    cat_orig = st.selectbox("Categoría Reservada", list(diferenciales_usd.keys()))
    fecha_estancia = st.date_input("Fecha de Estancia", datetime.now())

with col2:
    habitacion = st.text_input("Habitación Asignada")
    noches = st.number_input("Noches de Upgrade", min_value=1, value=1)
    cat_dest = st.selectbox("Categoría de Upgrade", list(diferenciales_usd.keys()), index=1)

# --- LÓGICA DE CÁLCULO ---
# 1. Buscar Tarifa Base en la pestaña 'Tarifas'
tarifa_base_dia = 0
if not df_tarifas.empty:
    df_tarifas['Stay Date'] = pd.to_datetime(df_tarifas['Stay Date'])
    res = df_tarifas[df_tarifas['Stay Date'] == pd.to_datetime(fecha_estancia)]
    if not res.empty:
        tarifa_base_dia = res.iloc[0]['Current Rate']

# 2. Calcular Diferencia de Categoría
diff_usd = diferenciales_usd[cat_dest] - diferenciales_usd[cat_orig]

if diff_usd > 0:
    # Lógica: (Diferencial USD * Factor Descuento) * Tipo de Cambio * Impuestos (16% IVA + 3% ISH)
    factor_desc = 1 - (desc_actual / 100)
    precio_noche_mxn = (diff_usd * factor_desc) * tc_actual * 1.19
    total_estancia = precio_noche_mxn * noches

    st.divider()
    c1, c2 = st.columns(2)
    c1.metric("Adicional por Noche", f"${precio_noche_mxn:,.2f} MXN")
    c2.metric("Total Estancia", f"${total_estancia:,.2f} MXN")

    # --- GENERADOR DE PDF ---
    if st.button("📥 Generar Formato para Firma"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, "CONVENIO DE UPGRADE DE HABITACION", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font("Arial", size=11)
        pdf.cell(190, 8, f"Huesped: {cliente.upper()} | Reserva: {n_reserva}", ln=1)
        pdf.cell(190, 8, f"Habitacion: {habitacion} | Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=1)
        pdf.ln(5)
        
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(190, 10, f" DETALLES DEL CARGO ADICIONAL", ln=1, fill=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(190, 8, f" De: {cat_orig}  -->  A: {cat_dest}", ln=1)
        pdf.cell(190, 8, f" Cargo por noche (impuestos inc.): ${precio_noche_mxn:,.2f} MXN", ln=1)
        pdf.cell(190, 8, f" TOTAL POR {noches} NOCHES: ${total_estancia:,.2f} MXN", ln=1)
        
        pdf.ln(15)
        pdf.set_font("Arial", 'I', 9)
        pdf.multi_cell(0, 5, "Por medio de la presente, acepto el cambio de categoria y el cargo adicional mencionado arriba en mi cuenta principal. Entiendo que este cargo es independiente a mi tarifa original.")
        
        pdf.ln(30)
        y_firma = pdf.get_y()
        pdf.line(10, y_firma, 90, y_firma) # Línea Huésped
        pdf.line(110, y_firma, 190, y_firma) # Línea Recepción
        pdf.set_y(y_firma + 2)
        pdf.cell(80, 8, "Firma del Huesped", ln=0, align='C')
        pdf.set_x(110)
        pdf.cell(80, 8, "Firma Recepcionista / Front Desk", ln=1, align='C')

        pdf_output = pdf.output(dest='S').encode('latin-1')
        st.download_button(
            label="Clic para descargar PDF",
            data=pdf_output,
            file_name=f"Upsell_{habitacion}_{n_reserva}.pdf",
            mime="application/pdf"
        )
    
elif diff_usd < 0:
    st.error("⚠️ MOVIMIENTO NO PERMITIDO: La categoría seleccionada es menor a la reservada (Downgrade).")
else:
    st.warning("Selecciona una categoría superior para cotizar el upgrade.")
