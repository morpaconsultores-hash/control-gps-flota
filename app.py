import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import time, timedelta, datetime

# 1. CONFIGURACIÓN DE LA PÁGINA WEB
st.set_page_config(
    page_title="Control GPS vs Asistencia - Flota",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Sistema de Control: GPS vs. Asistencia Manual")
st.markdown(
    "Sube el reporte mensual del GPS y la planilla de asistencia de los choferes "
    "para cruzar horarios, auditar tiempos de espera y detectar desviaciones automáticamente."
)

# --- FUNCIONES AUXILIARES PARA CONVERTIR HORAS ---
def a_horas(valor):
    """Convierte formatos hh:mm:ss, horas de Excel o decimales a horas numéricas."""
    if pd.isna(valor) or valor == "":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, timedelta):
        return valor.total_seconds() / 3600.0
    if isinstance(valor, time):
        return valor.hour + valor.minute / 60.0 + valor.second / 3600.0
    if isinstance(valor, datetime):
        return valor.hour + valor.minute / 60.0 + valor.second / 3600.0

    texto = str(valor).strip()
    if ":" in texto:
        # Si Excel guardó fecha ficticia 1900-01-XX hh:mm:ss
        if " " in texto:
            texto = texto.split(" ")[-1]
        partes = texto.split(":")
        try:
            if len(partes) == 3:
                return int(partes[0]) + int(partes[1]) / 60.0 + float(partes[2]) / 3600.0
            elif len(partes) == 2:
                return int(partes[0]) + int(partes[1]) / 60.0
        except ValueError:
            return 0.0
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return 0.0


def generar_plantilla_asistencia():
    """Crea un archivo Excel modelo para que los choferes llenen su asistencia."""
    columnas = [
        "Fecha",
        "Patente",
        "Hora inicio",
        "Hora termino",
        "Tiempo de espera",
        "Horas de descanso",
        "Labores auxiliares"
    ]
    ejemplo = pd.DataFrame([
        ["2026-10-01", "SLLT28", "08:00:00", "18:00:00", "01:30:00", "01:00:00", "00:30:00"],
        ["2026-10-01", "VM350", "07:30:00", "19:30:00", "03:30:00", "01:00:00", "01:00:00"],
    ], columns=columnas)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        ejemplo.to_excel(writer, sheet_name="Asistencia", index=False)
    return buffer.getvalue()


# --- BARRA LATERAL CON PLANTILLA Y PARÁMETROS ---
with st.sidebar:
    st.header("⚙️ Configuración y Plantilla")
    st.markdown("¿Aún no tienes la planilla lista para los choferes? Descarga el formato oficial aquí:")
    st.download_button(
        label="📄 Descargar Plantilla Choferes (.xlsx)",
        data=generar_plantilla_asistencia(),
        file_name="Plantilla_Asistencia_Choferes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.markdown("---")
    tolerancia = st.slider(
        "Tolerancia de diferencia (horas)",
        min_value=0.0,
        max_value=3.0,
        value=0.5,
        step=0.25,
        help="Diferencia máxima permitida entre lo registrado por el GPS y lo declarado por el chofer antes de marcar alerta."
    )

# --- 2. CARGA DE ARCHIVOS EN PANTALLA ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Archivo del GPS (.xlsx)")
    archivo_gps = st.file_uploader("Sube el reporte mensual generado por el GPS", type=["xlsx"], key="gps")

with col2:
    st.subheader("2️⃣ Planilla de Asistencia (.xlsx o .csv)")
    archivo_asistencia = st.file_uploader("Sube la planilla manual de los choferes", type=["xlsx", "csv"], key="asist")

# --- 3. PROCESAMIENTO Y CRUCE AUTOMÁTICO ---
if archivo_gps is not None:
    try:
        xls_gps = pd.ExcelFile(archivo_gps)
        hojas = xls_gps.sheet_names

        # Leer hoja 'Resumen diario' (los encabezados reales están en la fila 5 -> skiprows=4)
        if "Resumen diario" in hojas:
            df_gps = pd.read_excel(archivo_gps, sheet_name="Resumen diario", skiprows=4)
        else:
            st.error("El archivo GPS no contiene la hoja 'Resumen diario'. Verifica el formato.")
            st.stop()

        # Limpiar filas vacías y estandarizar Fecha y Patente
        df_gps = df_gps.dropna(subset=["Fecha", "Patente"]).copy()
        df_gps["Fecha"] = pd.to_datetime(df_gps["Fecha"]).dt.strftime("%Y-%m-%d")
        df_gps["Patente"] = df_gps["Patente"].astype(str).str.strip().str.upper()

        # Convertir columnas de tiempo del GPS a horas numéricas
        df_gps["GPS_Ruta_Hrs"] = df_gps["Tiempo en ruta"].apply(a_horas).round(2)
        df_gps["GPS_Espera_Ruta_Hrs"] = df_gps["Tiempo en espera"].apply(a_horas).round(2)
        df_gps["GPS_Estacionamiento_Hrs"] = df_gps["Estacionamiento"].apply(a_horas).round(2)
        df_gps["GPS_Activo_Total_Hrs"] = (df_gps["GPS_Ruta_Hrs"] + df_gps["GPS_Espera_Ruta_Hrs"]).round(2)

        # Si solo se subió el GPS, mostrar resumen del GPS
        if archivo_asistencia is None:
            st.info("👆 Archivo GPS cargado correctamente. Ahora sube la **Planilla de Asistencia** para realizar el cruce.")
            st.subheader("📊 Vista previa: Resumen Diario GPS")
            st.dataframe(df_gps, use_container_width=True)

        # Si se subieron AMBOS archivos, ejecutar el cruce completo
        else:
            if archivo_asistencia.name.endswith(".csv"):
                df_asist = pd.read_csv(archivo_asistencia)
            else:
                df_asist = pd.read_excel(archivo_asistencia)

            # Permitir que la columna se llame 'Codigo de vehiculo' o 'Patente'
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

            # Calcular horas declaradas por el chofer
            df_asist["Inicio_Hrs"] = df_asist["Hora inicio"].apply(a_horas)
            df_asist["Termino_Hrs"] = df_asist["Hora termino"].apply(a_horas)
            df_asist["Jornada_Bruta_Hrs"] = np.where(
                df_asist["Termino_Hrs"] >= df_asist["Inicio_Hrs"],
                df_asist["Termino_Hrs"] - df_asist["Inicio_Hrs"],
                (24.0 - df_asist["Inicio_Hrs"]) + df_asist["Termino_Hrs"]
            ).round(2)

            df_asist["Chofer_Espera_Hrs"] = df_asist["Tiempo de espera"].apply(a_horas).round(2)
            df_asist["Chofer_Descanso_Hrs"] = df_asist["Horas de descanso"].apply(a_horas).round(2)
            df_asist["Chofer_Auxiliar_Hrs"] = df_asist["Labores auxiliares"].apply(a_horas).round(2)

            # Horas operativas netas declaradas (Jornada menos descanso)
            df_asist["Chofer_Operativo_Neto_Hrs"] = (
                df_asist["Jornada_Bruta_Hrs"] - df_asist["Chofer_Descanso_Hrs"]
            ).clip(lower=0).round(2)

            # CRUCE MAESTRO (MERGE) POR FECHA Y PATENTE
            df_cruce = pd.merge(
                df_gps,
                df_asist,
                on=["Fecha", "Patente"],
                how="outer",
                indicator=True
            )

            # Calcular diferencias clave
            df_cruce["Dif_Operativa_Hrs"] = (
                df_cruce["Chofer_Operativo_Neto_Hrs"].fillna(0) - df_cruce["GPS_Activo_Total_Hrs"].fillna(0)
            ).round(2)

            df_cruce["Dif_Espera_Hrs"] = (
                df_cruce["Chofer_Espera_Hrs"].fillna(0) - df_cruce["GPS_Espera_Ruta_Hrs"].fillna(0)
            ).round(2)

            # Reglas automáticas de auditoría
            def evaluar_estado(fila):
                if fila["_merge"] == "left_only":
                    if fila.get("GPS_Activo_Total_Hrs", 0) > 0:
                        return "❓ Falta reporte de chofer"
                    return "🅿️ Camión detenido sin turno"
                if fila["_merge"] == "right_only":
                    return "❓ Sin registros en GPS"
                if fila.get("GPS_Ruta_Hrs", 0) == 0 and fila.get("Jornada_Bruta_Hrs", 0) > 0:
                    return "🚨 Alerta: GPS sin movimiento en ruta"
                if abs(fila["Dif_Operativa_Hrs"]) > tolerancia or abs(fila["Dif_Espera_Hrs"]) > tolerancia:
                    return "⚠️ Revisar diferencia de horas"
                return "✅ Cuadra dentro de tolerancia"

            df_cruce["Estado_Auditoria"] = df_cruce.apply(evaluar_estado, axis=1)
            df_cruce = df_cruce.drop(columns=["_merge"])

            # --- 4. VISUALIZACIÓN EN PESTAÑAS ---
            st.success("✅ ¡Cruce completado con éxito!")

            # Filtro por vehículo
            patentes = ["Todas"] + sorted(df_cruce["Patente"].dropna().unique().tolist())
            patente_sel = st.selectbox("Filtrar por Patente / Vehículo:", patentes)
            df_vista = df_cruce if patente_sel == "Todas" else df_cruce[df_cruce["Patente"] == patente_sel]

            # Indicadores rápidos (KPIs)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Registros Evaluados", len(df_vista))
            m2.metric("Cuadran OK", int((df_vista["Estado_Auditoria"].str.startswith("✅")).sum()))
            m3.metric("Con Alertas / Diferencias", int((df_vista["Estado_Auditoria"].str.startswith(("⚠️", "🚨"))).sum()))
            m4.metric("Sin Reporte Chofer", int((df_vista["Estado_Auditoria"] == "❓ Falta reporte de chofer").sum()))

            tab1, tab2, tab3 = st.tabs(["🔍 Resultado Auditoría", "📡 Datos GPS Procesados", "📝 Asistencia Choferes"])
            with tab1:
                st.dataframe(df_vista, use_container_width=True)
            with tab2:
                st.dataframe(df_gps, use_container_width=True)
            with tab3:
                st.dataframe(df_asist, use_container_width=True)

            # --- 5. BOTÓN DE DESCARGA DEL EXCEL CONSOLIDADO ---
            st.markdown("---")
            salida = io.BytesIO()
            with pd.ExcelWriter(salida, engine="xlsxwriter") as writer:
                df_cruce.to_excel(writer, sheet_name="Auditoria_Cruce", index=False)
                df_gps.to_excel(writer, sheet_name="GPS_Resumen_Hrs", index=False)
                df_asist.to_excel(writer, sheet_name="Asistencia_Choferes", index=False)

            st.download_button(
                label="📥 Descargar Reporte de Auditoría Completo (.xlsx)",
                data=salida.getvalue(),
                file_name="Auditoria_GPS_vs_Asistencia.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Ocurrió un problema al procesar los archivos: {e}")
