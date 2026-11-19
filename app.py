import io
from datetime import datetime, time, timedelta
import numpy as np
import pandas as pd
import streamlit as st

# ==============================================================================
# 1. CONFIGURACIÓN GENERAL Y ESTILOS WEB (DESKTOP + MÓVIL)
# ==============================================================================
st.set_page_config(
    page_title="Control GPS vs Asistencia | Gestión de Flota",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        /* Tipografía y fondo limpio */
        .stApp {
            background-color: #f6f8fb;
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2.5rem;
            max-width: 1380px;
        }

        /* Encabezado ejecutivo */
        .hero-card {
            background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 100%);
            color: #ffffff;
            padding: 1.4rem 1.6rem;
            border-radius: 14px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.12);
            margin-bottom: 1.25rem;
        }
        .hero-title {
            font-size: 1.55rem;
            font-weight: 700;
            margin: 0 0 0.35rem 0;
            letter-spacing: -0.01em;
        }
        .hero-subtitle {
            font-size: 0.95rem;
            color: #dbeafe;
            margin: 0;
            line-height: 1.45;
        }

        /* Tarjeta de acceso por correo */
        .auth-box {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 1.6rem;
            box-shadow: 0 6px 20px rgba(15, 23, 42, 0.06);
            margin-top: 1rem;
        }
        .auth-badge {
            display: inline-block;
            background: #eff6ff;
            color: #1d4ed8;
            font-weight: 600;
            font-size: 0.8rem;
            padding: 0.25rem 0.65rem;
            border-radius: 999px;
            margin-bottom: 0.6rem;
        }

        /* Barra de sesión activa */
        .session-bar {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #16a34a;
            border-radius: 10px;
            padding: 0.65rem 1rem;
            margin-bottom: 1rem;
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 0.5rem;
            font-size: 0.88rem;
        }

        /* Botones más cómodos al tacto y en escritorio */
        .stButton > button, .stDownloadButton > button {
            border-radius: 8px !important;
            font-weight: 600 !important;
            min-height: 2.5rem !important;
        }

        /* Ajustes específicos para pantallas de celular */
        @media (max-width: 768px) {
            .block-container {
                padding-top: 0.9rem;
                padding-left: 0.75rem;
                padding-right: 0.75rem;
            }
            .hero-card {
                padding: 1.1rem 1.15rem;
                border-radius: 12px;
            }
            .hero-title {
                font-size: 1.22rem;
            }
            .hero-subtitle {
                font-size: 0.86rem;
            }
            .auth-box {
                padding: 1.15rem;
            }
            /* Pestañas desplazables en móvil sin apretarse */
            div[data-baseweb="tab-list"] {
                gap: 0.25rem !important;
                overflow-x: auto !important;
                flex-wrap: nowrap !important;
            }
            button[data-baseweb="tab"] {
                white-space: nowrap !important;
                font-size: 0.84rem !important;
                padding: 0.5rem 0.75rem !important;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==============================================================================
# 2. CONTROL DE ACCESO POR CORREO ELECTRÓNICO AUTORIZADO
# ==============================================================================
CORREOS_POR_DEFECTO = [
    "admin@flota.cl",
    "control@flota.cl",
]


def obtener_correos_autorizados() -> set[str]:
    correos = set(c.strip().lower() for c in CORREOS_POR_DEFECTO if c.strip())
    try:
        if "CORREOS_AUTORIZADOS" in st.secrets:
            extra = st.secrets["CORREOS_AUTORIZADOS"]
            if isinstance(extra, (list, tuple, set)):
                for item in extra:
                    if str(item).strip():
                        correos.add(str(item).strip().lower())
            elif isinstance(extra, str):
                for item in extra.split(","):
                    if item.strip():
                        correos.add(item.strip().lower())
    except Exception:
        pass
    return correos


if "correo_autorizado" not in st.session_state:
    st.session_state.correo_autorizado = None

correos_validos = obtener_correos_autorizados()

if not st.session_state.correo_autorizado:
    st.markdown(
        """
        <div class="hero-card">
            <p class="hero-title">🚛 Control GPS vs Asistencia de Flota</p>
            <p class="hero-subtitle">Acceso restringido a usuarios autorizados. Ingresa tu correo corporativo para continuar.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col_centro, _ = st.columns([1, 1.4, 1])
    with col_centro:
        st.markdown('<div class="auth-box">', unsafe_allow_html=True)
        st.markdown('<span class="auth-badge">🔒 ACCESO POR CORREO</span>', unsafe_allow_html=True)
        st.subheader("Iniciar sesión")
        st.caption("Solo los correos previamente habilitados por administración pueden operar el sistema.")

        with st.form("form_acceso_correo", clear_on_submit=False):
            correo_ingresado = st.text_input(
                "Correo electrónico",
                placeholder="nombre.apellido@empresa.cl",
            )
            btn_ingresar = st.form_submit_button("Verificar y entrar", use_container_width=True)

        if btn_ingresar:
            correo_limpio = correo_ingresado.strip().lower()
            if not correo_limpio or "@" not in correo_limpio:
                st.warning("Ingresa un correo electrónico válido.")
            elif correo_limpio in correos_validos:
                st.session_state.correo_autorizado = correo_limpio
                st.rerun()
            else:
                st.error("Tu correo no está autorizado para usar este sistema. Solicita acceso al administrador.")

        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()

# ==============================================================================
# 3. FUNCIONES AUXILIARES DE TIEMPO (FORMATO ESTRICTO hh:mm:ss)
# ==============================================================================
def duration_to_seconds(val):
    if pd.isna(val) or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val) * 3600.0
    if isinstance(val, timedelta):
        return val.total_seconds()
    if isinstance(val, (time, datetime)):
        return val.hour * 3600 + val.minute * 60 + val.second

    texto = str(val).strip()
    if ":" in texto:
        partes = texto.split(":")
        try:
            if len(partes) == 4:
                dias = int(partes[0])
                horas = int(partes[1])
                mins = int(partes[2])
                secs = float(partes[3])
                return dias * 86400 + horas * 3600 + mins * 60 + secs
            elif len(partes) == 3:
                return int(partes[0]) * 3600 + int(partes[1]) * 60 + float(partes[2])
            elif len(partes) == 2:
                return int(partes[0]) * 3600 + int(partes[1]) * 60
        except ValueError:
            return 0.0
    try:
        return float(texto.replace(",", ".")) * 3600.0
    except ValueError:
        return 0.0


def format_seconds_to_hms(seconds):
    if pd.isna(seconds) or seconds < 0:
        return "00:00:00"
    total_secs = int(round(seconds))
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_signed_seconds_to_hms(seconds):
    if pd.isna(seconds):
        return "00:00:00"
    sign = "-" if seconds < 0 else "+"
    total_secs = int(round(abs(seconds)))
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60
    return f"{sign}{hours:02d}:{minutes:02d}:{secs:02d}"


def generar_plantilla_asistencia():
    columnas = [
        "Fecha",
        "Patente",
        "Nombre Chofer",
        "Hora inicio",
        "Hora termino",
        "Tiempo de espera",
        "Horas de descanso",
        "Labores auxiliares",
    ]
    ejemplo = pd.DataFrame(
        [
            ["2026-10-01", "PCDB55", "Juan Pérez", "08:00:00", "18:00:00", "01:00:00", "01:00:00", "00:30:00"],
            ["2026-10-01", "SLLT28", "Carlos Soto", "07:30:00", "19:30:00", "02:00:00", "01:00:00", "01:00:00"],
        ],
        columns=columnas,
    )
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        ejemplo.to_excel(writer, sheet_name="Asistencia", index=False)
    return buffer.getvalue()


# ==============================================================================
# 4. ENCABEZADO PRINCIPAL Y SESIÓN ACTIVA
# ==============================================================================
st.markdown(
    """
    <div class="hero-card">
        <p class="hero-title">🚛 Sistema Web: Procesamiento de GPS y Auditoría de Flota</p>
        <p class="hero-subtitle">Define tus estacionamientos, procesa el reporte crudo de viajes, filtra por patente o fecha y audita la asistencia en formato <b>hh:mm:ss</b>.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

col_ses_info, col_ses_btn = st.columns([4, 1])
with col_ses_info:
    st.markdown(
        f"""
        <div class="session-bar">
            <span>✅ <b>Usuario autorizado:</b> {st.session_state.correo_autorizado}</span>
            <span style="color:#64748b;">Formato de tiempos: <b>hh:mm:ss</b></span>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col_ses_btn:
    if st.button("Cerrar sesión", use_container_width=True):
        st.session_state.correo_autorizado = None
        st.rerun()

# ==============================================================================
# 5. BARRA LATERAL: ESTACIONAMIENTOS DINÁMICOS Y PARÁMETROS
# ==============================================================================
with st.sidebar:
    st.header("📍 Estacionamientos")
    cant_estacionamientos = st.number_input(
        "¿Cuántos estacionamientos tiene?",
        min_value=1,
        max_value=15,
        value=2,
        step=1,
    )

    lista_estacionamientos = []
    for i in range(int(cant_estacionamientos)):
        default_name = "Guido Beck de Ramberga" if i == 0 else ("Ruta 5 en Freire" if i == 1 else f"Estacionamiento {i+1}")
        est = st.text_input(f"Estacionamiento {i+1}", value=default_name, key=f"est_{i}")
        if est.strip():
            lista_estacionamientos.append(est.strip())

    st.markdown("---")
    st.header("⚙️ Auditoría")
    tolerancia_hrs = st.slider("Tolerancia diferencia (horas)", 0.0, 3.0, 0.5, 0.25)

    st.markdown("---")
    st.download_button(
        label="📄 Descargar Plantilla Choferes (.xlsx)",
        data=generar_plantilla_asistencia(),
        file_name="Plantilla_Asistencia_Choferes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# ==============================================================================
# 6. CARGA DE ARCHIVOS
# ==============================================================================
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### 1️⃣ Reporte GPS (Detalle de viajes)")
    archivo_gps = st.file_uploader("Sube el Excel crudo del GPS", type=["xlsx"], key="gps")

with col2:
    st.markdown("#### 2️⃣ Planilla de Asistencia (Opcional)")
    archivo_asistencia = st.file_uploader("Sube la asistencia de choferes", type=["xlsx", "csv"], key="asist")

if archivo_gps is not None:
    try:
        df_raw = pd.read_excel(archivo_gps, sheet_name=0, header=None)

        registros_detalles = []
        vehiculo_actual = "DESCONOCIDO"

        for _, row in df_raw.iterrows():
            val_0 = str(row[0]).strip() if pd.notna(row[0]) else ""

            if any(p in val_0.upper() for p in ["PCDB55", "RBGP67", "SLLT28", "VM350"]):
                for patente_ref in ["PCDB55", "RBGP67", "SLLT28", "VM350"]:
                    if patente_ref in val_0.upper():
                        vehiculo_actual = patente_ref
                        break

            if pd.notna(row[0]) and pd.notna(row[1]) and ("-" in str(row[0]) or "/" in str(row[0])) and "Hora" not in str(row[0]):
                direccion = str(row[3]) if pd.notna(row[3]) else ""
                estado_mov = str(row[4]).lower() if pd.notna(row[4]) else ""
                duracion_str = row[2]
                duracion_secs = duration_to_seconds(duracion_str)

                es_estacionamiento = any(e.lower() in direccion.lower() for e in lista_estacionamientos if e)

                if es_estacionamiento:
                    clasificacion = "Estacionamiento"
                elif "movimiento" in estado_mov:
                    clasificacion = "Tiempo en ruta"
                else:
                    clasificacion = "Tiempo en espera"

                registros_detalles.append(
                    {
                        "Patente": vehiculo_actual,
                        "Fecha": pd.to_datetime(row[0]).strftime("%Y-%m-%d"),
                        "Hora Inicio": row[0],
                        "Hora Fin": row[1],
                        "Duración": duracion_str,
                        "Duracion_Secs": duracion_secs,
                        "Dirección": direccion,
                        "Clasificación": clasificacion,
                    }
                )

        df_eventos = pd.DataFrame(registros_detalles)

        if not df_eventos.empty:
            # --- PANEL DE FILTROS CON BOTONES EN ESPAÑOL ---
            with st.sidebar:
                st.markdown("---")
                st.header("🔎 Filtros")

                patentes_disponibles = sorted(df_eventos["Patente"].unique().tolist())

                if "patentes_filtro" not in st.session_state:
                    st.session_state.patentes_filtro = patentes_disponibles

                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    if st.button("Todas", use_container_width=True):
                        st.session_state.patentes_filtro = patentes_disponibles
                        for p in patentes_disponibles:
                            st.session_state[f"chk_{p}"] = True
                        st.rerun()
                with col_b2:
                    if st.button("Ninguna", use_container_width=True):
                        st.session_state.patentes_filtro = []
                        for p in patentes_disponibles:
                            st.session_state[f"chk_{p}"] = False
                        st.rerun()

                st.markdown("**Patentes:**")
                patentes_seleccionadas = []
                for p in patentes_disponibles:
                    key_chk = f"chk_{p}"
                    if key_chk not in st.session_state:
                        st.session_state[key_chk] = p in st.session_state.patentes_filtro
                    if st.checkbox(p, key=key_chk):
                        patentes_seleccionadas.append(p)
                st.session_state.patentes_filtro = patentes_seleccionadas

                st.markdown("---")
                min_f = pd.to_datetime(df_eventos["Fecha"]).min().date()
                max_f = pd.to_datetime(df_eventos["Fecha"]).max().date()
                rango_fechas = st.date_input(
                    "Rango de fechas",
                    value=(min_f, max_f),
                    min_value=min_f,
                    max_value=max_f,
                )

            df_filtrado = df_eventos.copy()
            if patentes_seleccionadas:
                df_filtrado = df_filtrado[df_filtrado["Patente"].isin(patentes_seleccionadas)]
            else:
                df_filtrado = df_filtrado.iloc[0:0]

            if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
                f_inicio, f_fin = rango_fechas
                df_filtrado = df_filtrado[
                    (pd.to_datetime(df_filtrado["Fecha"]).dt.date >= f_inicio)
                    & (pd.to_datetime(df_filtrado["Fecha"]).dt.date <= f_fin)
                ]

            # 1. RESUMEN DIARIO
            df_pivot = df_filtrado.pivot_table(
                index=["Fecha", "Patente"],
                columns="Clasificación",
                values="Duracion_Secs",
                aggfunc="sum",
                fill_value=0.0,
            ).reset_index()

            for col in ["Tiempo en ruta", "Tiempo en espera", "Estacionamiento"]:
                if col not in df_pivot.columns:
                    df_pivot[col] = 0.0

            df_pivot["Total Horas Monitoreadas Secs"] = (
                df_pivot["Tiempo en ruta"] + df_pivot["Tiempo en espera"] + df_pivot["Estacionamiento"]
            )

            df_resumen_diario = pd.DataFrame(
                {
                    "Fecha": df_pivot["Fecha"],
                    "Patente": df_pivot["Patente"],
                    "Tiempo en ruta": df_pivot["Tiempo en ruta"].apply(format_seconds_to_hms),
                    "Tiempo en espera": df_pivot["Tiempo en espera"].apply(format_seconds_to_hms),
                    "Estacionamiento": df_pivot["Estacionamiento"].apply(format_seconds_to_hms),
                    "Total Horas Monitoreadas": df_pivot["Total Horas Monitoreadas Secs"].apply(format_seconds_to_hms),
                }
            )

            # 2. TIEMPOS POR FECHA (TOTALES POR VEHÍCULO)
            df_totales_vehiculo_pivot = df_filtrado.pivot_table(
                index="Patente",
                columns="Clasificación",
                values="Duracion_Secs",
                aggfunc="sum",
                fill_value=0.0,
            ).reset_index()

            for col in ["Tiempo en ruta", "Tiempo en espera", "Estacionamiento"]:
                if col not in df_totales_vehiculo_pivot.columns:
                    df_totales_vehiculo_pivot[col] = 0.0

            df_totales_vehiculo_pivot["Espera Total Secs"] = (
                df_totales_vehiculo_pivot["Tiempo en espera"] + df_totales_vehiculo_pivot["Estacionamiento"]
            )
            df_totales_vehiculo_pivot["Tiempo Registrado Secs"] = (
                df_totales_vehiculo_pivot["Espera Total Secs"] + df_totales_vehiculo_pivot["Tiempo en ruta"]
            )

            df_totales_vehiculo = pd.DataFrame(
                {
                    "Vehiculo": df_totales_vehiculo_pivot["Patente"],
                    "Tiempo recorrido": df_totales_vehiculo_pivot["Tiempo en ruta"].apply(format_seconds_to_hms),
                    "Espera estacionamiento": df_totales_vehiculo_pivot["Estacionamiento"].apply(format_seconds_to_hms),
                    "Espera en ruta": df_totales_vehiculo_pivot["Tiempo en espera"].apply(format_seconds_to_hms),
                    "Espera total": df_totales_vehiculo_pivot["Espera Total Secs"].apply(format_seconds_to_hms),
                    "Tiempo registrado": df_totales_vehiculo_pivot["Tiempo Registrado Secs"].apply(format_seconds_to_hms),
                }
            )
        else:
            df_resumen_diario = pd.DataFrame()
            df_totales_vehiculo = pd.DataFrame()
            df_filtrado = pd.DataFrame()

        # --- MÉTRICAS RÁPIDAS ---
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("Estacionamientos definidos", len(lista_estacionamientos))
        with m2:
            st.metric("Patentes filtradas", len(patentes_seleccionadas) if not df_eventos.empty else 0)
        with m3:
            st.metric("Registros en resumen diario", len(df_resumen_diario))

        st.markdown("")

        # --- PESTAÑAS ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            [
                "📊 Resumen Diario",
                "📈 Tiempos por Fecha",
                "⏱️ Detalle GPS",
                "🔍 Cruce Asistencia",
                "📥 Descargar Excel",
            ]
        )

        with tab1:
            st.subheader("Resumen Diario por Patente y Fecha")
            st.caption(f"Estacionamientos activos: {', '.join(lista_estacionamientos) if lista_estacionamientos else 'Ninguno'}")
            if not df_resumen_diario.empty:
                st.dataframe(df_resumen_diario, use_container_width=True, hide_index=True)
            else:
                st.info("No hay registros para el filtro actual.")

        with tab2:
            st.subheader("Tiempos Totales por Vehículo")
            if not df_totales_vehiculo.empty:
                st.dataframe(df_totales_vehiculo, use_container_width=True, hide_index=True)
            else:
                st.info("No hay registros para el filtro actual.")

        with tab3:
            st.subheader("Detalle Procesado del GPS")
            if not df_filtrado.empty:
                df_detalle_vista = df_filtrado.drop(columns=["Duracion_Secs"]).copy()
                st.dataframe(df_detalle_vista, use_container_width=True, hide_index=True)
            else:
                st.info("No hay registros para el filtro actual.")

        with tab4:
            st.subheader("Auditoría: GPS vs Asistencia Manual")
            if archivo_asistencia is None:
                st.info("Sube la planilla de asistencia de choferes para comparar tiempos en formato hh:mm:ss.")
            else:
                if archivo_asistencia.name.endswith(".csv"):
                    df_asist = pd.read_csv(archivo_asistencia)
                else:
                    df_asist = pd.read_excel(archivo_asistencia)

                renombres = {}
                for col in df_asist.columns:
                    c_low = col.strip().lower()
                    if c_low in ["codigo de vehiculo", "código de vehículo", "vehiculo", "vehículo"]:
                        renombres[col] = "Patente"
                    elif c_low == "fecha":
                        renombres[col] = "Fecha"
                    elif c_low in ["nombre chofer", "chofer", "conductor", "nombre conductor"]:
                        renombres[col] = "Nombre Chofer"
                df_asist = df_asist.rename(columns=renombres)

                if "Nombre Chofer" not in df_asist.columns:
                    df_asist["Nombre Chofer"] = "No especificado"

                df_asist = df_asist.dropna(subset=["Fecha", "Patente"]).copy()
                df_asist["Fecha"] = pd.to_datetime(df_asist["Fecha"]).dt.strftime("%Y-%m-%d")
                df_asist["Patente"] = df_asist["Patente"].astype(str).str.strip().str.upper()

                df_gps_cruce = df_pivot[["Fecha", "Patente", "Tiempo en ruta", "Tiempo en espera"]].copy()
                df_gps_cruce["GPS_Activo_Secs"] = df_gps_cruce["Tiempo en ruta"] + df_gps_cruce["Tiempo en espera"]

                df_asist["Chofer_Inicio_Secs"] = df_asist["Hora inicio"].apply(duration_to_seconds)
                df_asist["Chofer_Termino_Secs"] = df_asist["Hora termino"].apply(duration_to_seconds)

                jornada_secs = np.where(
                    df_asist["Chofer_Termino_Secs"] >= df_asist["Chofer_Inicio_Secs"],
                    df_asist["Chofer_Termino_Secs"] - df_asist["Chofer_Inicio_Secs"],
                    (86400.0 - df_asist["Chofer_Inicio_Secs"]) + df_asist["Chofer_Termino_Secs"],
                )
                df_asist["Chofer_Jornada_Secs"] = jornada_secs
                df_asist["Chofer_Descanso_Secs"] = df_asist["Horas de descanso"].apply(duration_to_seconds)
                df_asist["Chofer_Neto_Secs"] = np.clip(
                    df_asist["Chofer_Jornada_Secs"] - df_asist["Chofer_Descanso_Secs"], 0, None
                )

                df_cruce = pd.merge(df_gps_cruce, df_asist, on=["Fecha", "Patente"], how="outer", indicator=True)
                df_cruce["Dif_Secs"] = df_cruce["Chofer_Neto_Secs"].fillna(0) - df_cruce["GPS_Activo_Secs"].fillna(0)

                df_cruce_display = pd.DataFrame(
                    {
                        "Fecha": df_cruce["Fecha"],
                        "Patente": df_cruce["Patente"],
                        "Nombre Chofer": df_cruce["Nombre Chofer"].fillna("Sin registro"),
                        "GPS Activo (Ruta+Espera)": df_cruce["GPS_Activo_Secs"].apply(format_seconds_to_hms),
                        "Hora Inicio Chofer": df_cruce["Hora inicio"],
                        "Hora Término Chofer": df_cruce["Hora termino"],
                        "Jornada Chofer Neta": df_cruce["Chofer_Neto_Secs"].apply(format_seconds_to_hms),
                        "Diferencia Horaria": df_cruce["Dif_Secs"].apply(format_signed_seconds_to_hms),
                        "_merge": df_cruce["_merge"],
                    }
                )

                tolerancia_secs = tolerancia_hrs * 3600.0

                def evaluar(f):
                    if f["_merge"] == "left_only":
                        return "❓ Falta reporte chofer"
                    if f["_merge"] == "right_only":
                        return "❓ Sin registro GPS"
                    if abs(f["Dif_Secs"]) > tolerancia_secs:
                        return "⚠️ Alerta diferencia de horas"
                    return "✅ Cuadra OK"

                df_cruce_display["Estado de Auditoría"] = df_cruce.apply(evaluar, axis=1)
                st.dataframe(df_cruce_display.drop(columns=["_merge"]), use_container_width=True, hide_index=True)

        with tab5:
            st.subheader("Exportar Reporte en Excel")
            st.caption("Descarga los resultados filtrados en un solo archivo Excel.")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                if not df_resumen_diario.empty:
                    df_resumen_diario.to_excel(writer, sheet_name="Resumen_Diario", index=False)
                if not df_totales_vehiculo.empty:
                    df_totales_vehiculo.to_excel(writer, sheet_name="Tiempos_Por_Fecha", index=False)
                if archivo_asistencia is not None and "df_cruce_display" in locals():
                    df_cruce_display.drop(columns=["_merge"], errors="ignore").to_excel(
                        writer, sheet_name="Auditoria_Cruce", index=False
                    )

            st.download_button(
                label="📥 Descargar Excel Consolidado",
                data=output.getvalue(),
                file_name="Reporte_Flota_Auditado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
else:
    st.info("Define tus estacionamientos en el panel lateral y sube el archivo GPS para comenzar.")

