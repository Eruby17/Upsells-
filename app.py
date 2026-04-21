import streamlit as st
from fpdf import FPDF
from datetime import datetime, timedelta
import pandas as pd
from streamlit_gsheets import GSheetsConnection
import re

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Upsell Pro - Casa Dorada", page_icon="🏨", layout="centered")

# --- 2. CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. INICIALIZACIÓN DE VARIABLES DE SEGURIDAD ---
df_tarifas = pd.DataFrame()
desc_actual = 62.0
tc_actual = 17.40

# --- 4. CARGAR CONFIGURACIÓN (Pestaña 'Config') ---
try:
    df_config = conn.read(worksheet="Config", ttl=0)
    if df_config is not None and not df_config.empty:
        df_config.columns = [str(c).strip().lower() for c in df_config.columns]
        df_config['parametro'] = df_config['parametro'].astype(str).str.strip().str.lower()
        
        # Extracción de valores
        desc_actual = float(df_config[df_config['parametro'] == 'descuento']['valor'].values[0])
        tc_actual = float(df_config[df_config['parametro'] == 'tc']['valor'].values[0])
except Exception as e:
    st.sidebar.warning(f"Usando valores por defecto (Config no leída): {e}")

# --- 5. CARGAR TARIFAS (Pestaña 'Tarifas' con Limpieza Extrema) ---
try:
    df_raw = conn.read(worksheet="Tarifas", ttl=0)
    
    if df_raw is not None and not df_raw.empty:
        # Limpiar nombres de columnas (quitar espacios invisibles)
        df_raw.columns = [str(c).strip() for c in df_raw.columns]
        
        def extraer_fecha_limpia(valor):
            texto = str(valor).strip().lower()
            # Busca el patrón DD/MM/YYYY o D/M/YYYY ignorando cualquier texto previo como 'mar'
            match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', texto)
            if match:
                fecha_str = match.group(1)
                try:
                    # Convertir a objeto fecha real (dayfirst=True para formato Latino/Europeo)
                    return pd.to_datetime(fecha_str, dayfirst=True).date()
                except:
                    return None
            return None

        df_raw['Fecha_Python'] = df_raw['Stay Date'].apply(extraer_fecha_limpia)
        # Solo nos quedamos con las que tengan fecha y tarifa válida
        df_tarifas = df_raw.dropna(subset=['Fecha_Python', 'Current Rate']).copy()
        df_tarifas['Current Rate'] = pd.to_numeric(df_tarifas['Current Rate'], errors='coerce')
    else:
        st.error("La pestaña 'Tarifas' parece estar vacía.")
except Exception as e:
    st.error(f"Error técnico al leer Tarifas: {e}")

# --- 6. DIFERENCIALES DUETTO ---
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

# --- 7. INTERFAZ DE USUARIO ---
st.title("🏨 Room Upgrade Agreement")
st.markdown("---")

with st.sidebar:
    st.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", width=180)
    st.subheader("Estrategia de Venta")
    st.metric("Descuento Aplicado", f"{desc_actual}%")
    st.metric("Tipo de Cambio", f"${tc_actual} MXN")
    if st.button("🔄 Sincronizar Google Drive"):
        st.cache_data.clear()
        st.rerun()

col1, col2 = st.columns(2)
with col1:
    cliente = st.text_input("Nombre del Huésped")
    cat_orig = st.selectbox("Categoría Original Reservada", list(diferenciales_usd.keys()))
    # Calendario de Rango
    rango = st.date_input(
        "Periodo de Estancia (Llegada - Salida)",
        value=(datetime.now().date(), (datetime.now() + timedelta(days=1)).date()),
        min_value=datetime.now().date()
    )

with col2:
    n_reserva = st.text_input("Número de Confirmación")
    cat_dest = st.selectbox("Categoría de Upgrade", list(diferenciales_usd.keys()), index=3)
    habitacion = st.text_input("Habitación Asignada")

# --- 8. LÓGICA DE CÁLCULO ---
if len(rango) == 2:
    check_in, check_out = rango
    noches = (check_out - check_in).days
    
    if noches > 0:
        tarifa_base = 0
        
        if not df_tarifas.empty:
            # Buscamos la tarifa que coincida exactamente con el día de llegada (Check-in)
            match = df_tarifas[df_tarifas['Fecha_Python'] == check_in]
            if not match.empty:
                tarifa_base = float(match.iloc[0]['Current Rate'])
        
        # CONTROL DE ERROR SI NO HAY TARIFA
        if tarifa_base <= 0:
            st.error(f"❌ ERROR CRÍTICO: No se encontraron tarifas cargadas para la fecha {check_in.strftime('%d/%m/%Y')}. Revisa la pestaña 'Tarifas'.")
        else:
            # SECUENCIA FINANCIERA SOLICITADA:
            # 1. Precio Total Noche Original = Base + Diff Orig
            total_orig = tarifa_base + diferenciales_usd[cat_orig]
            # 2. Precio Total Noche Upgrade = Base + Diff Dest
            total_upg = tarifa_base + diferenciales_usd[cat_dest]
            # 3. Diferencia Bruta a pagar
            diff_bruta = total_upg - total_orig
            
            if diff_bruta > 0:
                # 4. Aplicamos Descuento
                factor_desc = 1 - (desc_actual / 100)
                precio_con_desc = diff_bruta * factor_desc
                # 5. Aplicamos 30% de Impuestos
                precio_final_noche_usd = precio_con_desc * 1.30
                
                # Totales finales
                total_usd = precio_final_noche_usd * noches
                total_mxn = total_usd * tc_actual

                st.success(f"Estancia calculada: {noches} noche(s).")
                c1, c2 = st.columns(2)
                c1.metric("Total USD (30% Tax Inc.)", f"${total_usd:,.2f}")
                c2.metric("Total MXN (30% Tax Inc.)", f"${total_mxn:,.2f}")

                # --- 9. GENERACIÓN DE PDF ---
                if st.button("📝 Generar Acuerdo PDF"):
                    pdf = FPDF()
                    pdf.add_page()
                    # Logo
                    try: pdf.image("https://cdn2.paraty.es/casa-dorada/images/89eeeacd45ffd2e", 10, 8, 45)
                    except: pass
                    
                    pdf.ln(20)
                    pdf.set_font("Arial", 'B', 16)
                    pdf.cell(0, 10, "ROOM UPGRADE AGREEMENT", ln=True, align='C')
                    pdf.ln(10)
                    
                    pdf.set_font("Arial", 'B', 10)
                    pdf.set_fill_color(240, 240, 240)
                    pdf.cell(190, 8, " GUEST & STAY DETAILS", ln=True, fill=True)
                    pdf.set_font("Arial", size=10)
                    pdf.cell(95, 8, f" Guest: {cliente.upper()}", border='B')
                    pdf.cell(95, 8, f" Confirmation: {n_reserva}", border='B', ln=True)
                    pdf.cell(95, 8, f" Arrival: {check_in.strftime('%b %d, %Y')}", border='B')
                    pdf.cell(95, 8, f" Departure: {check_out.strftime('%b %d, %Y')}", border='B', ln=True)
                    pdf.cell(95, 8, f" Room: {habitacion}", border='B')
                    pdf.cell(95, 8, f" Nights: {noches}", border='B', ln=True)
                    pdf.ln(5)
                    
                    pdf.set_font("Arial", 'B', 10)
                    pdf.cell(190, 8, " UPGRADE INFORMATION", ln=True, fill=True)
                    pdf.set_font("Arial", size=10)
                    pdf.cell(190, 8, f" From: {cat_orig}", ln=True)
                    pdf.cell(190, 8, f" To Category: {cat_dest}", ln=True)
                    pdf.ln(10)
                    
                    pdf.set_font("Arial", 'B', 12)
                    pdf.cell(190, 10, " TOTAL ADDITIONAL CHARGE (30% TAX INCLUDED)", ln=True)
                    pdf.set_font("Arial", 'B', 15)
                    pdf.cell(95, 15, f" USD ${total_usd:,.2f}", border=1, align='C')
                    pdf.cell(95, 15, f" MXN ${total_mxn:,.2f}", border=1, ln=True, align='C')
                    
                    pdf.ln(10)
                    pdf.set_font("Arial", size=9)
                    pdf.multi_cell(0, 5, "I authorize Casa Dorada Los Cabos Resort & Spa to apply these charges to my room account. I understand that the total in MXN is calculated based on the hotel's exchange rate.")
                    
                    pdf.ln(30)
                    y = pdf.get_y()
                    pdf.line(10, y, 90, y)
                    pdf.line(110, y, 190, y)
                    pdf.set_y(y + 2)
                    pdf.set_font("Arial", 'B', 9)
                    pdf.cell(80, 5, "Guest Signature", align='C')
                    pdf.set_x(110)
                    pdf.cell(80, 5, "Front Desk Representative", align='C')

                    # Descarga
                    pdf_out = pdf.output(dest='S').encode('latin-1')
                    st.download_button("📥 Descargar PDF Ahora", pdf_out, f"Upsell_{n_reserva}.pdf", "application/pdf")
            else:
                st.warning("⚠️ La categoría de destino no representa un upgrade económico.")
    else:
        st.info("Seleccione llegada y salida en el calendario.")
