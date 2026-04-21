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
try:
    df_config = conn.read(worksheet="Config", ttl="0") 
    desc_actual = float(df_config.loc[df_config['parametro'] == 'descuento', 'valor'].values[0])
    tc_actual = float(df_config.loc[df_config['parametro'] == 'tc', 'valor'].values[0])
except Exception:
    desc_actual = 55.0
    tc_actual = 18.0

# --- CARGAR TARIFAS BASE (Opcional si se requiere consulta) ---
try:
    df_tarifas = conn.read(worksheet="Tarifas", ttl="1h")
except Exception:
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

# --- BARRA LATERAL INFORMATIVA ---
with st.sidebar:
    st.header("📊 Estrategia de Venta")
    st.metric("Descuento Aplicado", f"{desc_actual}%")
    st.metric("T.C. de Venta", f"${tc_actual} MXN")
    st.divider()
    st.caption("Revenue Manager: Edite la pestaña 'Config' en Drive para actualizar estos valores.")

# --- INTERFAZ DEL RECEPCIONISTA ---
st.title("🏨 Cotizador de Upsells")

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Nombre del Huésped")
    n_reserva = st.text_input("Número de Reserva")
    cat_orig = st.selectbox("Categoría Reservada", list(diferenciales_usd.keys()))

with col2:
    habitacion = st.text_input("Habitación")
    noches = st.number_input("Noches de Upgrade", min_value=1, value=1)
    cat_dest = st.selectbox("Categoría de Upgrade", list(diferenciales_usd.keys()), index=1)

# --- LÓGICA DE CÁLCULO ---
# Diferencia en USD (Tarifa de Duetto)
diff_usd_full = diferenciales_usd[cat_dest] - diferenciales_usd[cat_orig]

if diff_usd_full > 0:
    # 1. Aplicamos el descuento de estrategia al diferencial
    factor_desc = 1 - (desc_actual / 100)
    precio_noche_usd = diff_usd_full * factor_desc
    
    # 2. Convertimos a MXN y aplicamos impuestos (1.19 = 16% IVA + 3% ISH)
    precio_noche_mxn = precio_noche_usd * tc_actual * 1.19
    total_estancia_mxn = precio_noche_mxn * noches
    total_estancia_usd = precio_noche_usd * noches * 1.19 # USD con impuestos

    st.divider()
    
    # Mostrar resultados en ambas monedas
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Costo en USD")
        st.write(f"Por noche: **${precio_noche_usd:,.2f} USD** (+ imp)")
        st.metric("Total USD (Inc. Imp)", f"${total_estancia_usd:,.2f}")
        
    with c2:
        st.subheader("Costo en MXN")
        st.write(f"T.C. aplicado: **${tc_actual}**")
        st.metric("Total MXN (Inc. Imp)", f"${total_estancia_mxn:,.2f}")

    # --- GENERADOR DE PDF ---
    if st.button("📥 Generar Formato para Firma"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(190, 10, "CONVENIO DE UPGRADE DE HABITACION", ln=True, align='C')
        pdf.ln(10)
        
        pdf.set_font("Arial", size=11)
        pdf.cell(190, 8, f"Huesped: {cliente.upper()} | Reserva: {n_reserva}", ln=1)
        pdf.cell(190, 8, f"Habitacion: {habitacion} | Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=1)
        pdf.ln(5)
        
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(190, 10, f" DETALLES DEL CARGO ADICIONAL", ln=1, fill=True)
        pdf.set_font("Arial", size=11)
        pdf.cell(190, 8, f" De: {cat_orig}  -->  A: {cat_dest}", ln=1)
        pdf.cell(190, 8, f" Cargo total en USD (impuestos inc.): ${total_estancia_usd:,.2f} USD", ln=1)
        pdf.cell(190, 8, f" Cargo total en moneda nacional: ${total_estancia_mxn:,.2f} MXN", ln=1)
        pdf.cell(190, 8, f" Tipo de Cambio aplicado: ${tc_actual} MXN", ln=1)
        
        pdf.ln(15)
        pdf.set_font("Arial", 'I', 9)
        pdf.multi_cell(0, 5, "Acepto el cargo adicional mencionado arriba y autorizo al hotel a cargarlo a mi cuenta principal. El monto en moneda nacional podria variar segun el tipo de cambio del dia del pago final.")
        
        pdf.ln(30)
        y_firma = pdf.get_y()
        pdf.line(10, y_firma, 90, y_firma)
        pdf.line(110, y_firma, 190, y_firma)
        pdf.set_y(y_firma + 2)
        pdf.cell(80, 8, "Firma del Huesped", ln=0, align='C')
        pdf.set_x(110)
        pdf.cell(80, 8, "Firma Recepcionista", ln=1, align='C')

        pdf_output = pdf.output(dest='S').encode('latin-1')
        st.download_button(
            label="Clic para descargar PDF",
            data=pdf_output,
            file_name=f"Upsell_{habitacion}_{n_reserva}.pdf",
            mime="application/pdf"
        )
    
elif diff_usd_full < 0:
    st.error("⚠️ NO SE PERMITEN DOWNGRADES.")
else:
    st.warning("Selecciona una categoría superior.")
