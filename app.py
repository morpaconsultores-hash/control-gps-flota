import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import time, timedelta, datetime

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(
    page_title="Control GPS vs Asistencia - Flota",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Sistema Web: Procesamiento de GPS y Auditoría de Flota")
st.markdown(
    "Sistema definitivo para procesar reportes crudos de GPS, configurar estacionamientos de forma dinámica, "
    "visualizar reportes en formato **hh:mm:ss** y realizar la auditoría con la asistencia manual."
)

# --- FUNCIONES AUXILIARES DE TIEMPO ---
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
                secs = int(partes[3])
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

def a_horas_decimal(valor):
    return duration_to_seconds(valor) / 3600.0

def generar_plantilla_asistencia():
    columnas = ["Fecha", "Patente", "Nombre Chofer", "Hora inicio", "Hora termino", "Tiempo de espera", "Horas de descanso", "Labores auxiliares"]
    ejemplo = pd.DataFrame([
        ["2026-10-01", "PCDB55", "Juan Pérez", "08:00:00", "18:00:00", "01:00:00", "01:00:00", "00:30:00"],
        ["2026-10-01", "SLLT28", "Carlos Soto", "07:30:00", "19:30:00", "02:00:00", "01:00:00", "01:00:00"],
    ], columns=columnas)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        ejemplo.to_excel(writer, sheet_name="Asistencia", index=False)
    return buffer.getvalue()

# --- BARRA LATERAL: CONFIGURACIÓN DINÁMICA DE ESTACIONAMIENTOS ---
with st.sidebar:
    st.header("📍 Configuración de Estacionamientos")
    cant_estacionamientos = st.number_input("¿Cuántos estacionamientos desea definir?", min_value=1, max_value=10, value=2, step=1)
    
    lista_estacionamientos = []
    for i in range(int(cant_estacionamientos)):
        est = st.text_input(f"Nombre Estacionamiento {i+1}", value=f"Base {i+1}" if i > 0 else "Guido Beck de Ramberga")
        if est.strip():
            lista_estacionamientos.append(est.strip())

    st.markdown("---")
    st.header("⚙️ Parámetros de Auditoría")
    tolerancia_hrs = st.slider("Tolerancia diferencia horas (Asistencia)", 0.0, 3.0, 0.5, 0.25)
    
    st.markdown("---")
    st.download_button(
        label="📄 Descargar Plantilla Choferes (.xlsx)",
        data=generar_plantilla_asistencia(),
        file_name="Plantilla_Asistencia_Choferes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Archivo del GPS (Datos Crudos)")
    archivo_gps = st.file_uploader("Sube el Excel de Reporte de Viaje", type=["xlsx"], key="gps")

with col2:
    st.subheader("2️⃣ Planilla de Asistencia (Opcional)")
    archivo_asistencia = st.file_uploader("Sube la asistencia manual de choferes", type=["xlsx", "csv"], key="asist")

if archivo_gps is not None:
    try:
        df_raw = pd.read_excel(archivo_gps, sheet_name=0, header=None)

        # --- PARSER INTELIGENTE Y ROBUSTO PARA LOS VEHÍCULOS ---
        registros_detalles = []
        vehiculo_actual = "DESCONOCIDO"

        for idx, row in df_raw.iterrows():
            val_0 = str(row[0]).strip() if pd.notna(row[0]) else ""
            
            if any(p in val_0.upper() for p in ["PCDB55", "RBGP67", "SLLT28", "VM350"]):
                for patente_ref in ["PCDB55", "RBGP67", "SLLT28", "VM350"]:
                    if patente_ref in val_0.upper():
                        vehiculo_actual = patente_ref
                        break

            if pd.notna(row[0]) and pd.notna(row[1]) and ("-" in str(row[0]) or "/" in str(row[0])) and not "Hora" in str(row[0]):
                direccion = str(row[3]) if pd.notna(row[3]) else ""
                estado_mov = str(row[4]).lower() if pd.notna(row[4]) else ""
                duracion_str = row[2]
                duracion_secs = duration_to_seconds(duracion_str)

                # Clasificación estricta basada exactamente en los estacionamientos definidos por el usuario
                es_estacionamiento = any(e.lower() in direccion.lower() for e in lista_estacionamientos if e)

                if es_estacionamiento:
                    clasificacion = "Estacionamiento"
                elif "movimiento" in estado_mov:
                    clasificacion = "Tiempo en ruta"
                else:
                    clasificacion = "Tiempo en espera"

                registros_detalles.append({
                    "Patente": vehiculo_actual,
                    "Fecha": pd.to_datetime(row[0]).strftime("%Y-%m-%d"),
                    "Hora Inicio": row[0],
                    "Hora Fin": row[1],
                    "Duración": duracion_str,
                    "Duracion_Secs": duracion_secs,
                    "Dirección": direccion,
                    "Clasificación": clasificacion
                })

        df_eventos = pd.DataFrame(registros_detalles)

        if not df_eventos.empty:
            # --- PANEL DE FILTROS CON BOTONES EN ESPAÑOL ---
            with st.sidebar:
                st.markdown("---")
                st.header("🔍 Panel de Filtros")
                
                patentes_disponibles = sorted(df_eventos["Patente"].unique().tolist())
                
                st.markdown("**Seleccionar Patentes:**")
                patentes_seleccionadas = []
                
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    todas = st.button("Todas")
                with col_b2:
                    ninguna = st.button("Ninguna")
                
                if "patentes_filtro" not in st.session_state:
                    st.session_state.patentes_filtro = patentes_disponibles

                if todas:
                    st.session_state.patentes_filtro = patentes_disponibles
                if ninguna:
                    st.session_state.patentes_filtro = []

                for p in patentes_disponibles:
                    checked = p in st.session_state.patentes_filtro
                    if st.checkbox(p, value=checked, key=f"chk_{p}"):
                        if p not in patentes_seleccionadas:
                            patentes_seleccionadas.append(p)
                    else:
                        if p in patentes_seleccionadas:
                            patentes_seleccionadas.remove(p)
                st.session_state.patentes_filtro = patentes_seleccionadas

                st.markdown("---")
                min_f = pd.to_datetime(df_eventos["Fecha"]).min().date()
                max_f = pd.to_datetime(df_eventos["Fecha"]).max().date()
                rango_fechas = st.date_input("Filtrar por Rango de Fechas", value=(min_f, max_f), min_value=min_f, max_value=max_f)

            # Aplicar Filtros al DataFrame
            df_filtrado = df_eventos.copy()
            if patentes_seleccionadas:
                df_filtrado = df_filtrado[df_filtrado["Patente"].isin(patentes_seleccionadas)]
            else:
                df_filtrado = df_filtrado.iloc[0:0]
            
            if isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
                f_inicio, f_fin = rango_fechas
                df_filtrado = df_filtrado[(pd.to_datetime(df_filtrado["Fecha"]).dt.date >= f_inicio) & (pd.to_datetime(df_filtrado["Fecha"]).dt.date <= f_fin)]

            # 1. CONSTRUCCIÓN DE RESUMEN DIARIO
            df_pivot = df_filtrado.pivot_table(
                index=["Fecha", "Patente"],
                columns="Clasificación",
                values="Duracion_Secs",
                aggfunc="sum",
                fill_value=0.0
            ).reset_index()

            for col in ["Tiempo en ruta", "Tiempo en espera", "Estacionamiento"]:
                if col not in df_pivot.columns:
                    df_pivot[col] = 0.0

            df_pivot["Total Horas Monitoreadas Secs"] = df_pivot["Tiempo en ruta"] + df_pivot["Tiempo en espera"] + df_pivot["Estacionamiento"]
            
            df_resumen_diario = pd.DataFrame({
                "Fecha": df_pivot["Fecha"],
                "Patente": df_pivot["Patente"],
                "Tiempo en ruta": df_pivot["Tiempo en ruta"].apply(format_seconds_to_hms),
                "Tiempo en espera": df_pivot["Tiempo en espera"].apply(format_seconds_to_hms),
                "Estacionamiento": df_pivot["Estacionamiento"].apply(format_seconds_to_hms),
                "Total Horas Monitoreadas": df_pivot["Total Horas Monitoreadas Secs"].apply(format_seconds_to_hms)
            })

            # 2. CONSTRUCCIÓN DE TIEMPOS POR FECHA (Totales)
            df_totales_vehiculo_pivot = df_filtrado.pivot_table(
                index="Patente",
                columns="Clasificación",
                values="Duracion_Secs",
                aggfunc="sum",
                fill_value=0.0
            ).reset_index()

            for col in ["Tiempo en ruta", "Tiempo en espera", "Estacionamiento"]:
                if col not in df_totales_vehiculo_pivot.columns:
                    df_totales_vehiculo_pivot[col] = 0.0

            df_totales_vehiculo_pivot["Espera Total Secs"] = df_totales_vehiculo_pivot["Tiempo en espera"] + df_totales_vehiculo_pivot["Estacionamiento"]
            df_totales_vehiculo_pivot["Tiempo Registrado Secs"] = df_totales_vehiculo_pivot["Espera Total Secs"] + df_totales_vehiculo_pivot["Tiempo en ruta"]

            df_totales_vehiculo = pd.DataFrame({
                "Vehiculo": df_totales_vehiculo_pivot["Patente"],
                "Tiempo recorrido": df_totales_vehiculo_pivot["Tiempo en ruta"].apply(format_seconds_to_hms),
                "Espera estacionamiento": df_totales_vehiculo_pivot["Estacionamiento"].apply(format_seconds_to_hms),
                "Espera en ruta": df_totales_vehiculo_pivot["Tiempo en espera"].apply(format_seconds_to_hms),
                "Espera total": df_totales_vehiculo_pivot["Espera Total Secs"].apply(format_seconds_to_hms),
                "Tiempo registrado": df_totales_vehiculo_pivot["Tiempo Registrado Secs"].apply(format_seconds_to_hms)
            })
        else:
            df_resumen_diario = pd.DataFrame()
            df_totales_vehiculo = pd.DataFrame()
            df_filtrado = pd.DataFrame()

        # --- PESTAÑAS DE VISUALIZACIÓN ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Resumen Diario", 
            "📈 Tiempos por Fecha (Totales)", 
            "⏱️ Detalle Crudo GPS",
            "🔍 Cruce con Asistencia",
            "📥 Descargar Reporte"
        ])

        with tab1:
            st.subheader("Resumen Diario por Patente y Fecha")
            st.markdown(f"Estacionamientos activos: **{', '.join(lista_estacionamientos)}**. Tiempos en formato **hh:mm:ss**.")
            if not df_resumen_diario.empty:
                st.dataframe(df_resumen_diario, use_container_width=True, hide_index=True)
            else:
                st.warning("No hay datos para los filtros seleccionados.")

        with tab2:
            st.subheader("Tiempos Totales por Vehículo")
            if not df_totales_vehiculo.empty:
                st.dataframe(df_totales_vehiculo, use_container_width=True, hide_index=True)
            else:
                st.warning("No hay datos para mostrar.")

        with tab3:
            st.subheader("Detalle Crudo Procesado del GPS")
            if not df_filtrado.empty:
                st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

        with tab4:
            st.subheader("Auditoría: GPS vs Asistencia Manual (Tiempos en hh:mm:ss)")
            if archivo_asistencia is None:
                st.info("💡 Sube la **Planilla de Asistencia** de los choferes para realizar la comparación.")
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
                    (86400.0 - df_asist["Chofer_Inicio_Secs"]) + df_asist["Chofer_Termino_Secs"]
                )
                df_asist["Chofer_Jornada_Secs"] = jornada_secs
                df_asist["Chofer_Descanso_Secs"] = df_asist["Horas de descanso"].apply(duration_to_seconds)
                df_asist["Chofer_Neto_Secs"] = np.clip(df_asist["Chofer_Jornada_Secs"] - df_asist["Chofer_Descanso_Secs"], 0, None)

                df_cruce = pd.merge(df_gps_cruce, df_asist, on=["Fecha", "Patente"], how="outer", indicator=True)
                df_cruce["Dif_Secs"] = df_cruce["Chofer_Neto_Secs"].fillna(0) - df_cruce["GPS_Activo_Secs"].fillna(0)
                
                df_cruce_display = pd.DataFrame({
                    "Fecha": df_cruce["Fecha"],
                    "Patente": df_cruce["Patente"],
                    "Nombre Chofer": df_cruce["Nombre Chofer"].fillna("Sin registro"),
                    "GPS Activo (Ruta+Espera)": df_cruce["GPS_Activo_Secs"].apply(format_seconds_to_hms),
                    "Hora Inicio Chofer": df_cruce["Hora inicio"],
                    "Hora Término Chofer": df_cruce["Hora termino"],
                    "Jornada Chofer Neta": df_cruce["Chofer_Neto_Secs"].apply(format_seconds_to_hms),
                    "Diferencia Horaria": df_cruce["Dif_Secs"].apply(format_signed_seconds_to_hms),
                    "_merge": df_cruce["_merge"]
                })

                tolerancia_secs = tolerancia_hrs * 3600.0

                def evaluar(f):
                    if f["_merge"] == "left_only": return "❓ Falta reporte chofer"
                    if f["_merge"] == "right_only": return "❓ Sin registro GPS"
                    if abs(f["Dif_Secs"]) > tolerancia_secs: return "⚠️ Alerta diferencia de horas"
                    return "✅ Cuadra OK"

                df_cruce_display["Estado de Auditoría"] = df_cruce.apply(evaluar, axis=1)
                st.dataframe(df_cruce_display.drop(columns=["_merge"]), use_container_width=True, hide_index=True)

        with tab5:
            st.subheader("📥 Descargar Reportes Consolidados")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                if not df_resumen_diario.empty: df_resumen_diario.to_excel(writer, sheet_name="Resumen_Diario", index=False)
                if not df_totales_vehiculo.empty: df_totales_vehiculo.to_excel(writer, sheet_name="Tiempos_Por_Fecha", index=False)
                if archivo_asistencia is not None and 'df_cruce_display' in locals():
                    df_cruce_display.to_excel(writer, sheet_name="Auditoria_Cruce", index=False)

            st.download_button(
                label="📥 Descargar Excel Completo",
                data=output.getvalue(),
                file_name="Reporte_Flota_Auditado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
else:
    st.info("👆 Define tus estacionamientos a la izquierda y sube tu archivo de GPS para comenzar.")
