import streamlit as st
from fpdf import FPDF
from datetime import datetime
import json
import os

# --- PERSISTENCIA DE DATOS (Simulación de Base de Datos) ---
# Esto asegura que la info no se pierda entre usuarios
DB_FILE = "config_upsell.json"

def cargar_config():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {"desc_web": 55.0, "tipo_cambio": 18.0} # Valores por defecto

def guardar_config(desc, tc):
    with open(DB_FILE, "w") as f:
        json.dump({"desc_web": desc, "tipo_cambio": tc}, f)

config = cargar_config()

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨")

# --- DATOS EXTRAÍDOS DE TU IMAGEN (Diferenciales en USD) ---
# Basados en 'Standard Two Double Beds'
diferenciales_usd = {
    "Standard Two Double Beds": 0.0,
    "Junior Suite": 75.0,
    "Deluxe Suite": 0.0, # Según tu captura, está igual que la Standard
    "Executive Suite": 150.0,
    "One Bedroom Suite Garden": 225.0,
    "One Bedroom Suite": 300.0,
    "1 Bedroom Suite Plus": 375.0,
    "2 Bedroom Suite": 780.0,
    "Penthouse 1PH": 1125.0,
    "Penthouse 2PH": 1875.0,
    "Penthouse 3PH": 2625.0
}

# --- PANEL DE REVENUE (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Control de Revenue")
    pwd = st.text_input("Contraseña", type="password")
    if pwd == "Revenue2026":
        st.success("Acceso Autorizado")
        nuevo_desc = st.slider("Descuento Web (%)", 0, 90, int(config["desc_web"]))
        nuevo_tc = st.number_input("Tipo de Cambio (USD/MXN)", value=config["tipo_cambio"])
        if st.button("Guardar para todos"):
            guardar_config(float(nuevo_desc), nuevo_tc)
            st.rerun()
    else:
        st.info("Introduce clave para modificar estrategia.")

# --- INTERFAZ PRINCIPAL ---
st.title("🏨 Cotizador de Upsells")
st.caption(f"TC: ${config['tipo_cambio']} | Estrategia: {config['desc_web']}% desc.")

col1, col2 = st.columns(2)

with col1:
    cliente = st.text_input("Nombre del Huésped")
    n_reserva = st.text_input("Número de Reserva")
    cat_orig = st.selectbox("Categoría Reservada", list(diferenciales_usd.keys()))

with col2:
    habitacion = st.text_input("Habitación Asignada")
    noches = st.number_input("Noches", min_value=1, value=1)
    cat_dest = st.selectbox("Categoría de Upgrade", list(diferenciales_usd.keys()), index=1)

# --- LÓGICA DE CÁLCULO ---
# Calculamos la diferencia en USD, aplicamos descuento y convertimos a MXN con impuestos
def calcular_upsell():
    diff_usd = diferenciales_usd[cat_dest] - diferenciales_usd[cat_orig]
    factor_desc = 1 - (config["desc_web"] / 100)
    
    precio_noche_neto_mxn = (diff_usd * factor_desc) * config["tipo_cambio"]
    impuestos = 1.19 # 16% IVA + 3% ISH
    
    final_noche = precio_noche_neto_mxn * impuestos
    return final_noche, final_noche * noches

precio_noche, total_estancia = calcular_upsell()

st.divider()

# --- VALIDACIÓN DE DOWNGRADE ---
if precio_noche > 0:
    st.balloons()
    c1, c2 = st.columns(2)
    c1.metric("Adicional por Noche", f"${precio_noche:,.2f} MXN")
    c2.metric("Total por Estancia", f"${total_estancia:,.2f} MXN")

    # GENERAR PDF
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
    pdf.cell(190, 10, f" DETALLES DEL CAMBIO", ln=1, fill=True)
    pdf.cell(190, 8, f" De: {cat_orig}", ln=1)
    pdf.cell(190, 8, f" A: {cat_dest}", ln=1)
    pdf.cell(190, 8, f" Cargo por noche: ${precio_noche:,.2f} MXN", ln=1)
    pdf.cell(190, 8, f" TOTAL ADICIONAL: ${total_estancia:,.2f} MXN", ln=1)
    
    pdf.ln(15)
    pdf.set_font("Arial", 'I', 9)
    pdf.multi_cell(0, 5, "Autorizo al hotel a realizar el cargo mencionado arriba a mi cuenta por concepto de upgrade de habitacion.")
    
    # SECCIÓN DE FIRMAS
    pdf.ln(30)
    pdf.cell(90, 0.1, "", border=1) # Linea 1
    pdf.set_x(110)
    pdf.cell(90, 0.1, "", border=1, ln=1) # Linea 2
    
    pdf.cell(90, 8, "Firma del Huesped", ln=0, align='C')
    pdf.cell(10, 8, "", ln=0)
    pdf.cell(90, 8, "Firma Recepcionista", ln=1, align='C')

    pdf_output = pdf.output(dest='S').encode('latin-1')
    st.download_button("📥 Descargar Formato para Firma", pdf_output, f"Upsell_{n_reserva}.pdf", "application/pdf")

elif precio_noche == 0:
    st.info("Misma categoría seleccionada. No hay cargo.")
else:
    st.error("⚠️ MOVIMIENTO NO PERMITIDO: La categoría destino es menor a la reservada (Downgrade).")
