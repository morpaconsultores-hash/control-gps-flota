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

st.title("🚛 Sistema Web: Procesamiento de GPS y Auditoría")
st.markdown(
    "Configura los estacionamientos de la empresa, sube el reporte crudo del GPS y visualiza "
    "automáticamente los reportes formateados en horas, minutos y segundos (**hh:mm:ss**)."
)

# --- FUNCIONES AUXILIARES DE TIEMPO ---
def duration_to_seconds(val):
    """Convierte cualquier formato de duración del GPS a segundos totales."""
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
            if len(partes) == 4: # Formato días:horas:minutos:segundos (ej: 2:1:57:31)
                dias = int(partes[0])
                horas = int(partes[1])
                mins = int(partes[2])
                secs = int(partes[3])
                return dias * 86400 + horas * 3600 + mins * 60 + secs
            elif len(partes) == 3: # Formato horas:minutos:segundos
                return int(partes[0]) * 3600 + int(partes[1]) * 60 + float(partes[2])
            elif len(partes) == 2: # Formato horas:minutos
                return int(partes[0]) * 3600 + int(partes[1]) * 60
        except ValueError:
            return 0.0
    try:
        return float(texto.replace(",", ".")) * 3600.0
    except ValueError:
        return 0.0

def format_seconds_to_hms(seconds):
    """Convierte segundos totales a formato estricto hh:mm:ss."""
    if pd.isna(seconds) or seconds < 0:
        return "00:00:00"
    total_secs = int(round(seconds))
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def a_horas_decimal(valor):
    """Retorna horas en decimal para cálculos de asistencia."""
    return duration_to_seconds(valor) / 3600.0

def generar_plantilla_asistencia():
    columnas = ["Fecha", "Patente", "Hora inicio", "Hora termino", "Tiempo de espera", "Horas de descanso", "Labores auxiliares"]
    ejemplo = pd.DataFrame([
        ["2026-10-01", "PCDB55", "08:00:00", "18:00:00", "01:00:00", "01:00:00", "00:30:00"],
        ["2026-10-01", "SLLT28", "07:30:00", "19:30:00", "02:00:00", "01:00:00", "01:00:00"],
    ], columns=columnas)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        ejemplo.to_excel(writer, sheet_name="Asistencia", index=False)
    return buffer.getvalue()

# --- BARRA LATERAL: CONFIGURACIÓN PREVIA DE ESTACIONAMIENTOS ---
with st.sidebar:
    st.header("📍 Estacionamientos Definidos")
    st.markdown("Configura las bases antes de procesar el archivo del GPS:")
    estacion_1 = st.text_input("Estacionamiento 1", value="Guido Beck de Ramberga")
    estacion_2 = st.text_input("Estacionamiento 2", value="Ruta 5 en Freire")
    
    st.markdown("---")
    tolerancia = st.slider("Tolerancia diferencia horas (Asistencia)", 0.0, 3.0, 0.5, 0.25)
    
    st.markdown("---")
    st.download_button(
        label="📄 Descargar Plantilla Choferes (.xlsx)",
        data=generar_plantilla_asistencia(),
        file_name="Plantilla_Asistencia_Choferes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# --- 2. CARGA DE ARCHIVOS ---
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
        st.success(f"✅ ¡Archivo GPS cargado! Estacionamientos activos: **{estacion_1}** y **{estacion_2}**.")

        # --- PARSER INTELIGENTE Y ROBUSTO PARA LOS 4 VEHÍCULOS ---
        registros_detalles = []
        vehiculo_actual = "DESCONOCIDO"

        for idx, row in df_raw.iterrows():
            val_0 = str(row[0]).strip() if pd.notna(row[0]) else ""
            
            # Detectar patente o vehículo (incluso si viene con descripción larga como SLLT28-MITSUBISHI)
            if any(p in val_0.upper() for p in ["PCDB55", "RBGP67", "SLLT28", "VM350"]):
                for patente_ref in ["PCDB55", "RBGP67", "SLLT28", "VM350"]:
                    if patente_ref in val_0.upper():
                        vehiculo_actual = patente_ref
                        break

            # Detectar filas con intervalos de tiempo (Hora Inicio y Hora Fin)
            if pd.notna(row[0]) and pd.notna(row[1]) and ("-" in str(row[0]) or "/" in str(row[0])) and not "Hora" in str(row[0]):
                direccion = str(row[3]) if pd.notna(row[3]) else ""
                estado_mov = str(row[4]).lower() if pd.notna(row[4]) else ""
                duracion_str = row[2]
                duracion_secs = duration_to_seconds(duracion_str)

                # Clasificación según reglas de negocio y estacionamientos
                if estacion_1.lower() in direccion.lower() or estacion_2.lower() in direccion.lower():
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
            # 1. CONSTRUCCIÓN DE RESUMEN DIARIO
            df_pivot = df_eventos.pivot_table(
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
            
            # Formatear todas las columnas de tiempo a hh:mm:ss
            df_resumen_diario = pd.DataFrame({
                "Fecha": df_pivot["Fecha"],
                "Patente": df_pivot["Patente"],
                "Tiempo en ruta": df_pivot["Tiempo en ruta"].apply(format_seconds_to_hms),
                "Tiempo en espera": df_pivot["Tiempo en espera"].apply(format_seconds_to_hms),
                "Estacionamiento": df_pivot["Estacionamiento"].apply(format_seconds_to_hms),
                "Total Horas Monitoreadas": df_pivot["Total Horas Monitoreadas Secs"].apply(format_seconds_to_hms)
            })

            # 2. CONSTRUCCIÓN DE TIEMPOS POR FECHA (Totales por los 4 Vehículos)
            df_totales_vehiculo_pivot = df_eventos.pivot_table(
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
            st.markdown(f"Clasificación considerando estacionamientos en: **{estacion_1}** y **{estacion_2}**. Tiempos en formato **hh:mm:ss**.")
            if not df_resumen_diario.empty:
                st.dataframe(df_resumen_diario, use_container_width=True)
            else:
                st.warning("No hay datos suficientes para generar el resumen diario.")

        with tab2:
            st.subheader("Tiempos Totales por Vehículo (Todos los vehículos detectados)")
            if not df_totales_vehiculo.empty:
                st.dataframe(df_totales_vehiculo, use_container_width=True)
            else:
                st.warning("No hay datos para mostrar.")

        with tab3:
            st.subheader("Detalle Crudo Procesado del GPS")
            if not df_eventos.empty:
                st.dataframe(df_eventos, use_container_width=True)

        with tab4:
            st.subheader("Auditoría: GPS vs Asistencia Manual")
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
                df_asist = df_asist.rename(columns=renombres)

                df_asist = df_asist.dropna(subset=["Fecha", "Patente"]).copy()
                df_asist["Fecha"] = pd.to_datetime(df_asist["Fecha"]).dt.strftime("%Y-%m-%d")
                df_asist["Patente"] = df_asist["Patente"].astype(str).str.strip().str.upper()

                # Preparar base numérica para comparar con asistencia
                df_gps_cruce = df_pivot[["Fecha", "Patente", "Tiempo en ruta", "Tiempo en espera"]].copy()
                df_gps_cruce["GPS_Activo_Hrs"] = (df_gps_cruce["Tiempo en ruta"] + df_gps_cruce["Tiempo en espera"]) / 3600.0

                df_asist["Chofer_Inicio"] = df_asist["Hora inicio"].apply(a_horas_decimal)
                df_asist["Chofer_Termino"] = df_asist["Hora termino"].apply(a_horas_decimal)
                df_asist["Chofer_Jornada"] = np.where(
                    df_asist["Chofer_Termino"] >= df_asist["Chofer_Inicio"],
                    df_asist["Chofer_Termino"] - df_asist["Chofer_Inicio"],
                    (24.0 - df_asist["Chofer_Inicio"]) + df_asist["Chofer_Termino"]
                )
                df_asist["Chofer_Descanso"] = df_asist["Horas de descanso"].apply(a_horas_decimal)
                df_asist["Chofer_Neto"] = (df_asist["Chofer_Jornada"] - df_asist["Chofer_Descanso"]).clip(lower=0)

                df_cruce = pd.merge(df_gps_cruce, df_asist, on=["Fecha", "Patente"], how="outer", indicator=True)
                df_cruce["Dif_Horas"] = (df_cruce["Chofer_Neto"].fillna(0) - df_cruce["GPS_Activo_Hrs"].fillna(0)).round(2)

                def evaluar(f):
                    if f["_merge"] == "left_only": return "❓ Falta reporte chofer"
                    if f["_merge"] == "right_only": return "❓ Sin registro GPS"
                    if abs(f["Dif_Horas"]) > tolerancia: return "⚠️ Alerta diferencia de horas"
                    return "✅ Cuadra OK"

                df_cruce["Estado_Auditoria"] = df_cruce.apply(evaluar, axis=1)
                st.dataframe(df_cruce.drop(columns=["_merge"]), use_container_width=True)

        with tab5:
            st.subheader("📥 Descargar Reportes Consolidados")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                if not df_resumen_diario.empty: df_resumen_diario.to_excel(writer, sheet_name="Resumen_Diario", index=False)
                if not df_totales_vehiculo.empty: df_totales_vehiculo.to_excel(writer, sheet_name="Tiempos_Por_Fecha", index=False)
                if archivo_asistencia is not None and 'df_cruce' in locals():
                    df_cruce.to_excel(writer, sheet_name="Auditoria_Cruce", index=False)

            st.download_button(
                label="📥 Descargar Excel Completo",
                data=output.getvalue(),
                file_name="Reporte_Flota_Auditado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
else:
    st.info("👆 Configura los estacionamientos a la izquierda y sube tu archivo de GPS para comenzar.")
