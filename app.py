import os
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import streamlit as st
from fpdf import FPDF
from supabase import create_client


# =========================================================
# 1. CONFIGURACIÓN DE PÁGINA
# =========================================================

st.set_page_config(
    page_title="Cotizador de upsells - Casa Dorada",
    page_icon="🏨",
    layout="wide",
)


# =========================================================
# 2. CONFIGURACIÓN GENERAL
# =========================================================

PASSWORD_ADMIN = st.secrets.get("revenue_password", "Revenue2026")

MESES = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]

# Orden fijo de menor a mayor categoría.
# NO se ordena alfabéticamente ni por importe.
CATEGORIAS = [
    "Standard Two Double Beds",
    "Junior Suite",
    "Deluxe Suite",
    "Executive Suite",
    "One Bedroom Suite",
    "One Bedroom Plus",
    "One Bedroom Ocean Front",
    "Two Bedroom Suite",
    "Two Bedroom Ocean Front",
    "One Bedroom Penthouse",
    "Two Bedroom Penthouse",
    "Three Bedroom Penthouse",
]

ANIO_ACTUAL = date.today().year
ANIO_SIGUIENTE = ANIO_ACTUAL + 1
ANIOS_ADMIN = [ANIO_ACTUAL, ANIO_SIGUIENTE]

IMPUESTOS_SERVICIOS = 0.30


# =========================================================
# 3. CONEXIÓN SUPABASE
# =========================================================

@st.cache_resource(show_spinner=False)
def obtener_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["secret_key"]
    return create_client(url, key)


supabase = obtener_supabase()


# =========================================================
# 4. HELPERS
# =========================================================

def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def numero_seguro(valor, default=0.0):
    try:
        if valor is None or pd.isna(valor):
            return float(default)
        return float(valor)
    except (TypeError, ValueError):
        return float(default)


def fecha_segura(valor):
    if valor is None or pd.isna(valor):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    try:
        return pd.to_datetime(valor).date()
    except Exception:
        return None


# =========================================================
# 5. LECTURA DE DATOS DESDE SUPABASE
# =========================================================

@st.cache_data(ttl=300, show_spinner=False)
def cargar_config_anio(anio):
    respuesta = (
        obtener_supabase()
        .table("upsell_settings")
        .select("year,discount,exchange_rate")
        .eq("year", int(anio))
        .execute()
    )

    if respuesta.data:
        fila = respuesta.data[0]
        return {
            "year": int(fila["year"]),
            "discount": numero_seguro(fila.get("discount"), 60.0),
            "exchange_rate": numero_seguro(fila.get("exchange_rate"), 17.40),
        }

    return {
        "year": int(anio),
        "discount": 60.0,
        "exchange_rate": 17.40,
    }


@st.cache_data(ttl=300, show_spinner=False)
def cargar_tarifas_anio(anio):
    respuesta = (
        obtener_supabase()
        .table("upsell_rates")
        .select("year,month,category,amount")
        .eq("year", int(anio))
        .order("month")
        .execute()
    )

    if not respuesta.data:
        return pd.DataFrame(columns=["year", "month", "category", "amount"])

    df = pd.DataFrame(respuesta.data)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").fillna(anio).astype(int)
    df["month"] = pd.to_numeric(df["month"], errors="coerce").fillna(0).astype(int)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def cargar_periodos_anio(anio):
    inicio = f"{int(anio)}-01-01"
    fin = f"{int(anio)}-12-31"

    respuesta = (
        obtener_supabase()
        .table("upsell_special_periods")
        .select("id,name,start_date,end_date,discount")
        .lte("start_date", fin)
        .gte("end_date", inicio)
        .order("start_date")
        .execute()
    )

    return respuesta.data or []


@st.cache_data(ttl=300, show_spinner=False)
def cargar_periodos_rango(fecha_inicio_iso, fecha_fin_iso):
    respuesta = (
        obtener_supabase()
        .table("upsell_special_periods")
        .select("id,name,start_date,end_date,discount")
        .lte("start_date", fecha_fin_iso)
        .gte("end_date", fecha_inicio_iso)
        .order("start_date")
        .execute()
    )

    return respuesta.data or []


def construir_matriz_tarifas(df_long):
    if df_long is None or df_long.empty:
        return None

    matriz = pd.DataFrame(
        0.0,
        index=CATEGORIAS,
        columns=MESES,
        dtype=float,
    )

    for _, fila in df_long.iterrows():
        categoria = str(fila.get("category", "")).strip()
        mes = int(numero_seguro(fila.get("month"), 0))
        amount = numero_seguro(fila.get("amount"), 0.0)

        if categoria in CATEGORIAS and 1 <= mes <= 12:
            matriz.loc[categoria, MESES[mes - 1]] = amount

    matriz.index.name = "Categoría"
    return matriz


def preparar_editor_periodos(periodos):
    filas = []

    for periodo in periodos:
        filas.append(
            {
                "Nombre": str(periodo.get("name", "")),
                "Fecha Inicio": fecha_segura(periodo.get("start_date")),
                "Fecha Fin": fecha_segura(periodo.get("end_date")),
                "Descuento Especial (%)": numero_seguro(periodo.get("discount"), 0.0),
            }
        )

    return pd.DataFrame(
        filas,
        columns=[
            "Nombre",
            "Fecha Inicio",
            "Fecha Fin",
            "Descuento Especial (%)",
        ],
    )


def obtener_descuento_para_fecha(fecha_noche, descuento_base, periodos):
    descuentos_especiales = []

    for periodo in periodos:
        inicio = fecha_segura(periodo.get("start_date"))
        fin = fecha_segura(periodo.get("end_date"))

        if inicio and fin and inicio <= fecha_noche <= fin:
            descuentos_especiales.append(
                numero_seguro(periodo.get("discount"), descuento_base)
            )

    # Si accidentalmente se superponen dos periodos de alta demanda,
    # usamos el MENOR descuento, que produce la tarifa de upsell más alta.
    if descuentos_especiales:
        return min(descuentos_especiales), True

    return float(descuento_base), False


# =========================================================
# 6. FUNCIONES DE ESCRITURA EN SUPABASE
# =========================================================

def guardar_configuracion(anio, descuento, tipo_cambio):
    registro = {
        "year": int(anio),
        "discount": float(descuento),
        "exchange_rate": float(tipo_cambio),
        "updated_at": ahora_iso(),
    }

    (
        supabase
        .table("upsell_settings")
        .upsert(registro, on_conflict="year")
        .execute()
    )


def guardar_matriz_tarifas(anio, matriz):
    registros = []
    timestamp = ahora_iso()

    for numero_mes, nombre_mes in enumerate(MESES, start=1):
        for categoria in CATEGORIAS:
            valor = numero_seguro(matriz.loc[categoria, nombre_mes], 0.0)

            if valor < 0:
                raise ValueError(
                    f"La tarifa de {categoria} en {nombre_mes} no puede ser negativa."
                )

            registros.append(
                {
                    "year": int(anio),
                    "month": int(numero_mes),
                    "category": categoria,
                    "amount": round(float(valor), 2),
                    "updated_at": timestamp,
                }
            )

    (
        supabase
        .table("upsell_rates")
        .upsert(
            registros,
            on_conflict="year,month,category",
        )
        .execute()
    )


def copiar_anio(origen, destino):
    df_origen = cargar_tarifas_anio(origen)

    if df_origen.empty:
        raise ValueError(f"No existen tarifas en {origen} para copiar.")

    timestamp = ahora_iso()
    registros = []

    for _, fila in df_origen.iterrows():
        registros.append(
            {
                "year": int(destino),
                "month": int(fila["month"]),
                "category": str(fila["category"]),
                "amount": round(numero_seguro(fila["amount"], 0.0), 2),
                "updated_at": timestamp,
            }
        )

    (
        supabase
        .table("upsell_rates")
        .upsert(
            registros,
            on_conflict="year,month,category",
        )
        .execute()
    )

    config_origen = cargar_config_anio(origen)
    guardar_configuracion(
        destino,
        config_origen["discount"],
        config_origen["exchange_rate"],
    )


def crear_anio_vacio(anio):
    timestamp = ahora_iso()
    registros = []

    for numero_mes in range(1, 13):
        for categoria in CATEGORIAS:
            registros.append(
                {
                    "year": int(anio),
                    "month": numero_mes,
                    "category": categoria,
                    "amount": 0.0,
                    "updated_at": timestamp,
                }
            )

    (
        supabase
        .table("upsell_rates")
        .upsert(
            registros,
            on_conflict="year,month,category",
        )
        .execute()
    )


def guardar_periodos_del_anio(anio, df_editor):
    existentes = cargar_periodos_anio(anio)
    ids_existentes = [p.get("id") for p in existentes if p.get("id") is not None]

    if ids_existentes:
        (
            supabase
            .table("upsell_special_periods")
            .delete()
            .in_("id", ids_existentes)
            .execute()
        )

    nuevos = []

    for _, fila in df_editor.iterrows():
        nombre = str(fila.get("Nombre", "")).strip()
        fecha_inicio = fecha_segura(fila.get("Fecha Inicio"))
        fecha_fin = fecha_segura(fila.get("Fecha Fin"))
        descuento = numero_seguro(fila.get("Descuento Especial (%)"), -1)

        fila_totalmente_vacia = (
            not nombre
            and fecha_inicio is None
            and fecha_fin is None
            and descuento < 0
        )

        if fila_totalmente_vacia:
            continue

        if not nombre:
            raise ValueError("Todos los periodos deben tener un nombre.")

        if fecha_inicio is None or fecha_fin is None:
            raise ValueError(f"El periodo '{nombre}' debe tener fecha de inicio y fin.")

        if fecha_fin < fecha_inicio:
            raise ValueError(
                f"En '{nombre}', la fecha final no puede ser anterior a la inicial."
            )

        if not 0 <= descuento <= 100:
            raise ValueError(
                f"El descuento de '{nombre}' debe estar entre 0% y 100%."
            )

        nuevos.append(
            {
                "name": nombre,
                "start_date": fecha_inicio.isoformat(),
                "end_date": fecha_fin.isoformat(),
                "discount": round(float(descuento), 2),
            }
        )

    if nuevos:
        (
            supabase
            .table("upsell_special_periods")
            .insert(nuevos)
            .execute()
        )


# =========================================================
# 7. SIDEBAR
# =========================================================

with st.sidebar:
    st.header("⚙️ Operaciones")

    if st.button("🔄 Refrescar datos", use_container_width=True):
        st.cache_data.clear()
        st.toast("Datos actualizados desde Supabase", icon="✅")
        st.rerun()

    st.divider()
    st.header("🔑 Administración")

    modo_admin = st.checkbox("Entrar como Revenue Manager")
    admin_autorizado = False

    if modo_admin:
        clave = st.text_input("Contraseña", type="password")

        if clave == PASSWORD_ADMIN:
            admin_autorizado = True
            st.success("Acceso Autorizado")
        elif clave:
            st.error("Contraseña Incorrecta")
    else:
        config_sidebar = cargar_config_anio(ANIO_ACTUAL)
        st.metric("Descuento Operativo", f"{config_sidebar['discount']:.0f}%")
        st.metric(
            "Tipo de Cambio",
            f"${config_sidebar['exchange_rate']:.2f} MXN",
        )


# =========================================================
# 8. PANEL REVENUE
# =========================================================

if admin_autorizado:
    st.title("⚙️ Revenue Management - Upsells")

    st.caption(
        "Las tarifas de cada año permanecen separadas. "
        "Solo se permite administrar el año actual y el siguiente."
    )

    anio_admin = st.radio(
        "Año de tarifas",
        options=ANIOS_ADMIN,
        format_func=lambda x: (
            f"{x} — Año actual" if x == ANIO_ACTUAL else f"{x} — Próximo año"
        ),
        horizontal=True,
        key="anio_admin",
    )

    st.divider()

    df_tarifas_admin = cargar_tarifas_anio(anio_admin)
    config_admin = cargar_config_anio(anio_admin)

    # -----------------------------------------------------
    # Si el siguiente año todavía no tiene tarifas
    # -----------------------------------------------------

    if df_tarifas_admin.empty:
        st.warning(f"Todavía no existen tarifas configuradas para {anio_admin}.")

        col_copiar, col_vacio = st.columns(2)

        with col_copiar:
            if st.button(
                f"📋 Copiar tarifas {anio_admin - 1} → {anio_admin}",
                type="primary",
                use_container_width=True,
            ):
                try:
                    with st.spinner("Copiando tarifas..."):
                        copiar_anio(anio_admin - 1, anio_admin)
                        st.cache_data.clear()
                    st.success(f"Tarifas {anio_admin} creadas correctamente.")
                    st.rerun()
                except Exception as err:
                    st.error(f"No se pudieron copiar las tarifas: {err}")

        with col_vacio:
            if st.button(
                f"Crear {anio_admin} desde cero",
                use_container_width=True,
            ):
                try:
                    with st.spinner("Creando matriz vacía..."):
                        crear_anio_vacio(anio_admin)
                        st.cache_data.clear()
                    st.success(f"Matriz {anio_admin} creada correctamente.")
                    st.rerun()
                except Exception as err:
                    st.error(f"No se pudo crear el año: {err}")

    else:
        matriz_admin = construir_matriz_tarifas(df_tarifas_admin)

        st.subheader(f"Configuración {anio_admin}")

        with st.form(f"form_tarifas_{anio_admin}"):
            col_desc, col_tc = st.columns(2)

            with col_desc:
                desc_input = st.number_input(
                    "Descuento Base (%)",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(config_admin["discount"]),
                    step=1.0,
                    help=(
                        "Este descuento se aplica cuando la fecha no pertenece "
                        "a un periodo especial de alta demanda."
                    ),
                )

            with col_tc:
                tc_input = st.number_input(
                    "Tipo de Cambio Oficial",
                    min_value=1.0,
                    max_value=100.0,
                    value=float(config_admin["exchange_rate"]),
                    step=0.1,
                )

            st.divider()
            st.subheader(f"Tarifas / valores por categoría — {anio_admin}")
            st.caption(
                "Habitaciones ordenadas de menor a mayor categoría. "
                "Cada celda puede modificarse directamente; cambiar Junior Suite "
                "ya no recalcula automáticamente las demás categorías."
            )

            editor_admin = matriz_admin.reset_index()

            config_columnas = {
                "Categoría": st.column_config.TextColumn(
                    "Categoría",
                    disabled=True,
                    width="large",
                )
            }

            for mes in MESES:
                config_columnas[mes] = st.column_config.NumberColumn(
                    mes,
                    min_value=0.0,
                    step=5.0,
                    format="$%.2f",
                )

            df_editado = st.data_editor(
                editor_admin,
                hide_index=True,
                use_container_width=True,
                disabled=["Categoría"],
                column_config=config_columnas,
                key=f"editor_tarifas_{anio_admin}",
            )

            guardar_tarifas = st.form_submit_button(
                f"💾 Guardar cambios {anio_admin}",
                type="primary",
                use_container_width=True,
            )

        if guardar_tarifas:
            try:
                matriz_guardar = (
                    df_editado
                    .set_index("Categoría")
                    .reindex(CATEGORIAS)
                )

                matriz_guardar = matriz_guardar[MESES].apply(
                    pd.to_numeric,
                    errors="coerce",
                ).fillna(0.0)

                with st.spinner("Guardando en Supabase..."):
                    guardar_configuracion(anio_admin, desc_input, tc_input)
                    guardar_matriz_tarifas(anio_admin, matriz_guardar)
                    st.cache_data.clear()

                st.success(f"Cambios de {anio_admin} guardados correctamente.")
                st.toast("Tarifas sincronizadas con Supabase", icon="✅")
                st.rerun()

            except Exception as err:
                st.error(f"Error al guardar tarifas: {err}")

        # -------------------------------------------------
        # PERIODOS DE ALTA DEMANDA
        # -------------------------------------------------

        st.divider()
        st.subheader("📅 Periodos de alta demanda")
        st.info(
            "En estas fechas NO se cambia la matriz de tarifas. "
            "Se sustituye únicamente el descuento base por un descuento especial. "
            "Menor descuento = tarifa de upsell más alta."
        )

        periodos_admin = cargar_periodos_anio(anio_admin)
        df_periodos = preparar_editor_periodos(periodos_admin)

        with st.form(f"form_periodos_{anio_admin}"):
            df_periodos_editado = st.data_editor(
                df_periodos,
                num_rows="dynamic",
                hide_index=True,
                use_container_width=True,
                column_config={
                    "Nombre": st.column_config.TextColumn(
                        "Nombre del periodo",
                        width="large",
                    ),
                    "Fecha Inicio": st.column_config.DateColumn(
                        "Fecha Inicio",
                        format="YYYY-MM-DD",
                    ),
                    "Fecha Fin": st.column_config.DateColumn(
                        "Fecha Fin",
                        format="YYYY-MM-DD",
                    ),
                    "Descuento Especial (%)": st.column_config.NumberColumn(
                        "Descuento Especial (%)",
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                    ),
                },
                key=f"editor_periodos_{anio_admin}",
            )

            guardar_periodos = st.form_submit_button(
                "💾 Guardar periodos de alta demanda",
                use_container_width=True,
            )

        if guardar_periodos:
            try:
                with st.spinner("Guardando periodos..."):
                    guardar_periodos_del_anio(anio_admin, df_periodos_editado)
                    st.cache_data.clear()

                st.success("Periodos de alta demanda guardados correctamente.")
                st.rerun()

            except Exception as err:
                st.error(f"Error al guardar periodos: {err}")

        st.caption(
            "Si dos periodos especiales se superponen, el cotizador aplicará "
            "el menor porcentaje de descuento."
        )

    st.divider()


# =========================================================
# 9. INTERFAZ PRINCIPAL PARA RECEPCIÓN
# =========================================================

st.title("🏨 Cotizador de Upsells - Casa Dorada")

col_nom, col_fol = st.columns(2)

with col_nom:
    cliente = st.text_input("Nombre del Huésped", value="")

with col_fol:
    n_reserva = st.text_input("Número de Confirmación", value="")

fecha_hoy = date.today()
fecha_maxima = date(ANIO_SIGUIENTE, 12, 31)

col_in, col_out = st.columns(2)

with col_in:
    check_in = st.date_input(
        "Check-in",
        fecha_hoy,
        max_value=fecha_maxima,
    )

with col_out:
    check_out = st.date_input(
        "Check-out",
        fecha_hoy + timedelta(days=1),
        max_value=fecha_maxima + timedelta(days=1),
    )

noches = (check_out - check_in).days if check_out and check_in else 1

col_cat1, col_cat2 = st.columns(2)

with col_cat1:
    cat_orig = st.selectbox(
        "Categoría Original",
        CATEGORIAS,
        index=0,
    )

with col_cat2:
    cat_dest = st.selectbox(
        "Upgrade a Categoría",
        CATEGORIAS,
        index=1,
    )

st.divider()

ejecutar_calculo = st.button("🧮 Calcular", type="primary")


# =========================================================
# 10. CÁLCULO BASADO EN SUPABASE
# =========================================================

if noches <= 0:
    st.error("La fecha de salida debe ser posterior a la de entrada.")

else:
    if ejecutar_calculo or "p_noche_estacional" in st.session_state:
        try:
            # -------------------------------------------------
            # AÑOS UTILIZADOS EN LA ESTANCIA
            # -------------------------------------------------

            fechas_noches = [
                check_in + timedelta(days=n)
                for n in range(noches)
            ]

            anios_estancia = sorted({fecha.year for fecha in fechas_noches})

            anios_permitidos = set(ANIOS_ADMIN)
            anios_fuera_rango = [a for a in anios_estancia if a not in anios_permitidos]

            if anios_fuera_rango:
                raise ValueError(
                    "La estancia contiene un año que todavía no está habilitado "
                    "en Revenue Management."
                )

            # -------------------------------------------------
            # CARGAR TARIFAS Y CONFIGURACIONES POR AÑO
            # -------------------------------------------------

            tarifas_lookup = {}
            configs_lookup = {}

            for anio in anios_estancia:
                df_anio = cargar_tarifas_anio(anio)

                if df_anio.empty:
                    raise ValueError(
                        f"No existen tarifas configuradas para {anio}. "
                        f"Revenue debe configurar ese año antes de cotizar."
                    )

                configs_lookup[anio] = cargar_config_anio(anio)

                for _, fila in df_anio.iterrows():
                    clave = (
                        int(fila["year"]),
                        int(fila["month"]),
                        str(fila["category"]),
                    )
                    tarifas_lookup[clave] = numero_seguro(fila["amount"], 0.0)

            ultima_noche = check_out - timedelta(days=1)
            periodos_estancia = cargar_periodos_rango(
                check_in.isoformat(),
                ultima_noche.isoformat(),
            )

            # -------------------------------------------------
            # CALCULAR NOCHE POR NOCHE
            # -------------------------------------------------

            total_neto_sugerido = 0.0
            detalle_noches = []
            noches_especiales = 0

            for fecha_noche in fechas_noches:
                anio = fecha_noche.year
                mes = fecha_noche.month

                clave_orig = (anio, mes, cat_orig)
                clave_dest = (anio, mes, cat_dest)

                if clave_orig not in tarifas_lookup:
                    raise ValueError(
                        f"Falta la tarifa de '{cat_orig}' para "
                        f"{MESES[mes - 1]} {anio}."
                    )

                if clave_dest not in tarifas_lookup:
                    raise ValueError(
                        f"Falta la tarifa de '{cat_dest}' para "
                        f"{MESES[mes - 1]} {anio}."
                    )

                tarifa_orig = tarifas_lookup[clave_orig]
                tarifa_dest = tarifas_lookup[clave_dest]

                gap_noche = max(float(tarifa_dest) - float(tarifa_orig), 0.0)

                descuento_base = configs_lookup[anio]["discount"]
                descuento_noche, es_especial = obtener_descuento_para_fecha(
                    fecha_noche,
                    descuento_base,
                    periodos_estancia,
                )

                if es_especial:
                    noches_especiales += 1

                neto_noche = gap_noche * (1 - descuento_noche / 100)
                total_neto_sugerido += neto_noche

                detalle_noches.append(
                    {
                        "Fecha": fecha_noche,
                        "Año": anio,
                        "Mes": MESES[mes - 1],
                        "Valor Original": tarifa_orig,
                        "Valor Upgrade": tarifa_dest,
                        "GAP": gap_noche,
                        "Descuento": descuento_noche,
                        "Neto sugerido": neto_noche,
                        "Periodo especial": "Sí" if es_especial else "No",
                    }
                )

            # Promedio por noche de los netos calculados individualmente.
            tarifa_sugerida_neto = total_neto_sugerido / noches
            st.session_state["p_noche_estacional"] = tarifa_sugerida_neto

            tarifa_sugerida_impuestos = tarifa_sugerida_neto * IMPUESTOS_SERVICIOS
            tarifa_sugerida_con_impuestos = (
                tarifa_sugerida_neto + tarifa_sugerida_impuestos
            )

            # El tipo de cambio de la cotización se toma del año del check-in.
            tc_actual = configs_lookup[check_in.year]["exchange_rate"]

            # -------------------------------------------------
            # RESETEAR TARIFA MANUAL AL PULSAR CALCULAR
            # -------------------------------------------------

            if ejecutar_calculo:
                st.session_state["modo_tarifa_manual"] = False
                st.session_state.pop("tarifa_manual_input", None)

            if "modo_tarifa_manual" not in st.session_state:
                st.session_state["modo_tarifa_manual"] = False

            # -------------------------------------------------
            # TARIFA FINAL POR DEFECTO = TARIFA SUGERIDA
            # -------------------------------------------------

            p_noche_neto = tarifa_sugerida_neto
            impuesto_por_noche = tarifa_sugerida_impuestos
            p_noche_con_impuestos = tarifa_sugerida_con_impuestos

            st.subheader("Tarifa sugerida por cotizador")

            st.metric(
                "Tarifa sugerida por cotizador (USD / noche con impuestos)",
                f"${tarifa_sugerida_con_impuestos:,.2f}",
            )

            if noches_especiales > 0:
                st.info(
                    f"Se aplicó descuento especial de alta demanda en "
                    f"{noches_especiales} de {noches} noche(s)."
                )

            with st.expander("Ver detalle del cálculo por noche"):
                df_detalle = pd.DataFrame(detalle_noches)
                st.dataframe(
                    df_detalle,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Valor Original": st.column_config.NumberColumn(format="$%.2f"),
                        "Valor Upgrade": st.column_config.NumberColumn(format="$%.2f"),
                        "GAP": st.column_config.NumberColumn(format="$%.2f"),
                        "Descuento": st.column_config.NumberColumn(format="%.2f%%"),
                        "Neto sugerido": st.column_config.NumberColumn(format="$%.2f"),
                    },
                )

            # -------------------------------------------------
            # MODIFICACIÓN MANUAL
            # -------------------------------------------------

            if not st.session_state["modo_tarifa_manual"]:
                if st.button("Modificar tarifa manual", use_container_width=True):
                    st.session_state["modo_tarifa_manual"] = True
                    st.rerun()

            else:
                tarifa_minima = float(round(tarifa_sugerida_con_impuestos, 2))

                st.warning(
                    f"La tarifa manual no puede ser menor a la tarifa sugerida "
                    f"por cotizador: ${tarifa_minima:,.2f} USD por noche."
                )

                valor_manual_guardado = st.session_state.get("tarifa_manual_input")

                if (
                    valor_manual_guardado is None
                    or float(valor_manual_guardado) < tarifa_minima
                ):
                    st.session_state["tarifa_manual_input"] = tarifa_minima

                tarifa_manual = st.number_input(
                    "Nueva tarifa USD / noche (Con impuestos)",
                    min_value=tarifa_minima,
                    step=5.0,
                    format="%.2f",
                    key="tarifa_manual_input",
                )

                if float(tarifa_manual) < tarifa_minima:
                    st.error(
                        f"La tarifa ingresada no puede ser menor a "
                        f"${tarifa_minima:,.2f} USD por noche."
                    )
                else:
                    p_noche_con_impuestos = float(tarifa_manual)
                    p_noche_neto = p_noche_con_impuestos / (1 + IMPUESTOS_SERVICIOS)
                    impuesto_por_noche = p_noche_con_impuestos - p_noche_neto

                    if p_noche_con_impuestos > tarifa_minima:
                        st.success(
                            f"✅ Tarifa manual aplicada: "
                            f"${p_noche_con_impuestos:,.2f} USD por noche."
                        )

                if st.button(
                    "↩️ Usar tarifa sugerida por cotizador",
                    use_container_width=True,
                ):
                    st.session_state["modo_tarifa_manual"] = False
                    st.session_state.pop("tarifa_manual_input", None)
                    st.rerun()

            # -------------------------------------------------
            # TOTALES
            # -------------------------------------------------

            total_usd_con_impuestos = p_noche_con_impuestos * noches
            total_mxn_con_impuestos = total_usd_con_impuestos * tc_actual
            c_reserva = n_reserva if n_reserva.strip() else "Sin_Numero"

            st.divider()

            res1, res2, res3, res4 = st.columns(4)
            res1.metric("Noches", f"{noches}")
            res2.metric(
                "Tarifa Final USD / Noche (Con Impuestos)",
                f"${p_noche_con_impuestos:,.2f}",
            )
            res3.metric(
                "Total Estancia (USD)",
                f"${total_usd_con_impuestos:,.2f} USD",
            )
            res4.metric(
                "Total Estancia (MXN)",
                f"${total_mxn_con_impuestos:,.2f} MXN",
            )

            st.caption(
                f"Conversión MXN usando tipo de cambio configurado para "
                f"{check_in.year}: ${tc_actual:.2f} MXN por USD."
            )

            st.divider()

            # =================================================
            # 11. GENERACIÓN DE PDF
            # =================================================

            def generar_pdf_bytes():
                pdf = FPDF()
                pdf.add_page()

                logo_path = "logo 12.png"
                if os.path.exists(logo_path):
                    pdf.image(logo_path, x=10, y=8, w=42)

                pdf.ln(15)
                pdf.set_font("Helvetica", "B", 16)
                pdf.cell(
                    0,
                    10,
                    "ROOM UPGRADE AGREEMENT",
                    align="R",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

                pdf.set_font("Helvetica", "", 10)
                pdf.cell(
                    0,
                    5,
                    f"Date: {datetime.now().strftime('%d/%m/%Y')}",
                    align="R",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.ln(10)

                # Información del huésped
                pdf.set_fill_color(30, 55, 110)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(
                    0,
                    8,
                    "   GUEST INFORMATION",
                    fill=True,
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

                pdf.set_text_color(0, 0, 0)
                pdf.set_font("Helvetica", "", 11)
                pdf.ln(2)

                g_name = cliente.upper() if cliente else "VALUED GUEST"

                pdf.cell(
                    95,
                    8,
                    f"Guest: {g_name}".encode("latin-1", "replace").decode("latin-1"),
                )
                pdf.cell(
                    95,
                    8,
                    f"Confirmation: {c_reserva}".encode("latin-1", "replace").decode("latin-1"),
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.cell(95, 8, f"Check-in: {check_in.strftime('%d %b, %Y')}")
                pdf.cell(
                    95,
                    8,
                    f"Check-out: {check_out.strftime('%d %b, %Y')}",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.cell(
                    95,
                    8,
                    f"Number of Nights: {noches}",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.ln(5)

                # Detalles del upgrade
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_fill_color(30, 55, 110)
                pdf.cell(
                    0,
                    8,
                    "   ROOM UPGRADE DETAILS",
                    fill=True,
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

                pdf.set_text_color(0, 0, 0)
                pdf.ln(2)
                pdf.set_fill_color(240, 240, 240)
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(60, 10, "   Original Room:", border="B", fill=True)
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(
                    130,
                    10,
                    f"   {cat_orig}".encode("latin-1", "replace").decode("latin-1"),
                    border="B",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

                pdf.set_fill_color(230, 240, 255)
                pdf.set_font("Helvetica", "B", 10)
                pdf.cell(60, 12, "   UPGRADED TO:", border="B", fill=True)
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(
                    130,
                    12,
                    f"   {cat_dest}".encode("latin-1", "replace").decode("latin-1"),
                    border="B",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )
                pdf.ln(5)

                # Desglose
                pdf.set_font("Helvetica", "", 11)
                pdf.cell(120, 8, "Upgrade Fee per Night (Net):")
                pdf.cell(
                    70,
                    8,
                    f"USD ${p_noche_neto:,.2f}",
                    align="R",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

                pdf.cell(120, 8, "Taxes & Services per Night (30%):")
                pdf.cell(
                    70,
                    8,
                    f"USD ${impuesto_por_noche:,.2f}",
                    align="R",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(
                    120,
                    8,
                    f"Total Upgrade Fee per Night (Taxes Inc. x {noches} nights):",
                )
                pdf.cell(
                    70,
                    8,
                    f"USD ${p_noche_con_impuestos:,.2f}",
                    align="R",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(120, 10, "GRAND TOTAL UPGRADE FEE:", border="T")
                pdf.set_font("Helvetica", "B", 14)
                pdf.cell(
                    70,
                    10,
                    f"USD ${total_usd_con_impuestos:,.2f}",
                    border="T",
                    align="R",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

                pdf.set_font("Helvetica", "I", 10)
                pdf.cell(
                    120,
                    8,
                    f"Exchange Rate / Tipo de Cambio (1 USD = {tc_actual} MXN):",
                )
                pdf.set_font("Helvetica", "B", 12)
                pdf.cell(
                    70,
                    8,
                    f"MXN ${total_mxn_con_impuestos:,.2f}",
                    align="R",
                    new_x="LMARGIN",
                    new_y="NEXT",
                )

                pdf.ln(15)
                pdf.set_font("Helvetica", "I", 9)

                terminos_texto = (
                    "Terms: This upgrade is non-refundable and applies for the entire stay. "
                    "In the event of an early departure, no refund will be issued for the upsell.\n"
                    "Este upgrade no es reembolsable y aplica por la estancia completa. "
                    "En caso de salida anticipada, no aplicara ningun reembolso por el upsell."
                )

                pdf.multi_cell(
                    0,
                    5,
                    terminos_texto.encode("latin-1", "replace").decode("latin-1"),
                )

                pdf.ln(25)
                pdf.line(10, pdf.get_y(), 85, pdf.get_y())
                pdf.line(125, pdf.get_y(), 200, pdf.get_y())
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(75, 10, "Guest Signature", align="C")
                pdf.set_x(125)
                pdf.cell(75, 10, "Front Office Representative", align="C")

                return bytes(pdf.output())

            st.download_button(
                label="📥 Descargar PDF",
                data=generar_pdf_bytes(),
                file_name=f"Upgrade_{c_reserva}.pdf",
                mime="application/pdf",
            )

        except Exception as err:
            st.error(f"No se pudo calcular la cotización: {err}")
