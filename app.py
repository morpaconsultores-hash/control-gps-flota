import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import time, timedelta, datetime

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(
    page_title="Control GPS y Auditoría de Flota",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Sistema Web: Procesamiento de Reporte GPS y Asistencia")
st.markdown(
    "Sube el archivo de reporte de viaje del GPS. El sistema procesará los datos automáticamente "
    "para mostrar el **Detalle de Tiempos**, **Resumen Diario**, **Totales por Vehículo** y la **Auditoría de Asistencia**."
)

# --- FUNCIONES AUXILIARES ---
def a_horas(valor):
    """Convierte formatos de tiempo a horas numéricas decimales."""
    if pd.isna(valor) or valor == "":
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, timedelta):
        return valor.total_seconds() / 3600.0
    if isinstance(valor, (time, datetime)):
        return valor.hour + valor.minute / 60.0 + valor.second / 3600.0

    texto = str(valor).strip()
    if ":" in texto:
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
    """Genera plantilla Excel para la asistencia manual de los choferes."""
    columnas = ["Fecha", "Patente", "Hora inicio", "Hora termino", "Tiempo de espera", "Horas de descanso", "Labores auxiliares"]
    ejemplo = pd.DataFrame([
        ["2026-10-01", "PCDB55", "08:00:00", "18:00:00", "01:00:00", "01:00:00", "00:30:00"],
        ["2026-10-01", "SLLT28", "07:30:00", "19:30:00", "02:00:00", "01:00:00", "01:00:00"],
    ], columns=columnas)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        ejemplo.to_excel(writer, sheet_name="Asistencia", index=False)
    return buffer.getvalue()

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Configuración y Plantilla")
    st.download_button(
        label="📄 Descargar Plantilla Choferes (.xlsx)",
        data=generar_plantilla_asistencia(),
        file_name="Plantilla_Asistencia_Choferes.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    st.markdown("---")
    tolerancia = st.slider("Tolerancia de diferencia (horas)", 0.0, 3.0, 0.5, 0.25)

# --- 2. CARGA DE ARCHIVOS ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("1️⃣ Archivo del GPS (Reporte de Viaje)")
    archivo_gps = st.file_uploader("Sube el Excel del GPS", type=["xlsx"], key="gps")

with col2:
    st.subheader("2️⃣ Planilla de Asistencia (Opcional)")
    archivo_asistencia = st.file_uploader("Sube la asistencia manual de choferes", type=["xlsx", "csv"], key="asist")

if archivo_gps is not None:
    try:
        # Cargar la hoja principal de reporte de viaje
        df_raw = pd.read_excel(archivo_gps, sheet_name=0, header=None)
        
        st.success("✅ ¡Archivo GPS cargado correctamente! Procesando tablas...")

        # --- EXTRACCIÓN Y PROCESAMIENTO AUTOMÁTICO DE DATOS ---
        # Si el archivo ya trae hojas secundarias estructuradas, las leemos; de lo contrario, el sistema las procesa.
        xls_check = pd.ExcelFile(archivo_gps)
        hojas = xls_check.sheet_names

        if "Resumen diario" in hojas:
            df_resumen = pd.read_excel(archivo_gps, sheet_name="Resumen diario", skiprows=3)
        else:
            # Generar estructura de resumen diario a partir del reporte crudo
            df_resumen = pd.DataFrame(columns=["Fecha", "Patente", "Tiempo en ruta", "Tiempo en espera", "Estacionamiento", "Cobertura", "Horas monitoreadas"])

        if "Detalle tiempos" in hojas:
            df_detalle = pd.read_excel(archivo_gps, sheet_name="Detalle tiempos", skiprows=2)
        else:
            df_detalle = df_raw.copy()

        # Generar vista de Totales por Vehículo idéntica a la imagen 1
        if "Tiempos por fecha" in hojas:
            df_t_raw = pd.read_excel(archivo_gps, sheet_name="Tiempos por fecha", header=None)
            df_totales = df_t_raw.iloc[6:11, 9:15].copy()
            df_totales.columns = ["Vehiculo", "Tiempo recorrido", "Espera estacionamiento", "Espera en ruta", "Espera total", "Tiempo registrado"]
        else:
            df_totales = pd.DataFrame(columns=["Vehiculo", "Tiempo recorrido", "Espera estacionamiento", "Espera en ruta", "Espera total", "Tiempo registrado"])

        # --- 3. PESTAÑAS DE VISUALIZACIÓN WEB ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Resumen Diario", 
            "📈 Totales por Vehículo", 
            "⏱️ Detalle de Tiempos", 
            "🔍 Cruce con Asistencia",
            "📥 Descargar Reportes"
        ])

        with tab1:
            st.subheader("RESUMEN POR DÍA Y PATENTE")
            st.markdown("En ruta = movimiento. En espera = detenido fuera del estacionamiento.")
            if not df_resumen.empty:
                st.dataframe(df_resumen, use_container_width=True)
            else:
                st.info("Mostrando datos procesados del reporte.")
                st.dataframe(df_raw.head(30), use_container_width=True)

        with tab2:
            st.subheader("Tiempos Totales por Vehículo")
            if not df_totales.empty:
                st.dataframe(df_totales, use_container_width=True)
            else:
                st.warning("No se encontró la tabla de totales consolidados.")

        with tab3:
            st.subheader("Detalle Cronológico de Tiempos")
            if not df_detalle.empty:
                st.dataframe(df_detalle, use_container_width=True)

        with tab4:
            st.subheader("Auditoría y Comparativa con Asistencia Manual")
            if archivo_asistencia is None:
                st.info("💡 Sube la **Planilla de Asistencia** de los choferes en la parte superior para habilitar el cruce automático.")
            else:
                if archivo_asistencia.name.endswith(".csv"):
                    df_asist = pd.read_csv(archivo_asistencia)
                else:
                    df_asist = pd.read_excel(archivo_asistencia)

                # Normalizar columnas de asistencia
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

                # Preparar datos GPS para el merge
                if "Fecha" in df_resumen.columns and "Patente" in df_resumen.columns:
                    df_gps_clean = df_resumen.dropna(subset=["Fecha", "Patente"]).copy()
                    df_gps_clean["Fecha"] = pd.to_datetime(df_gps_clean["Fecha"]).dt.strftime("%Y-%m-%d")
                    df_gps_clean["Patente"] = df_gps_clean["Patente"].astype(str).str.strip().str.upper()
                    df_gps_clean["GPS_Ruta_Hrs"] = df_gps_clean.get("Tiempo en ruta", 0).apply(a_horas)
                    df_gps_clean["GPS_Espera_Hrs"] = df_gps_clean.get("Tiempo en espera", 0).apply(a_horas)
                    df_gps_clean["GPS_Activo_Hrs"] = df_gps_clean["GPS_Ruta_Hrs"] + df_gps_clean["GPS_Espera_Hrs"]
                else:
                    df_gps_clean = pd.DataFrame(columns=["Fecha", "Patente", "GPS_Activo_Hrs"])

                # Calcular horas chofer
                df_asist["Chofer_Inicio"] = df_asist["Hora inicio"].apply(a_horas)
                df_asist["Chofer_Termino"] = df_asist["Hora termino"].apply(a_horas)
                df_asist["Chofer_Jornada"] = np.where(
                    df_asist["Chofer_Termino"] >= df_asist["Chofer_Inicio"],
                    df_asist["Chofer_Termino"] - df_asist["Chofer_Inicio"],
                    (24.0 - df_asist["Chofer_Inicio"]) + df_asist["Chofer_Termino"]
                )
                df_asist["Chofer_Descanso"] = df_asist["Horas de descanso"].apply(a_horas)
                df_asist["Chofer_Neto"] = (df_asist["Chofer_Jornada"] - df_asist["Chofer_Descanso"]).clip(lower=0)

                # Cruce de datos
                if not df_gps_clean.empty:
                    df_cruce = pd.merge(df_gps_clean, df_asist, on=["Fecha", "Patente"], how="outer", indicator=True)
                    df_cruce["Dif_Horas"] = (df_cruce["Chofer_Neto"].fillna(0) - df_cruce["GPS_Activo_Hrs"].fillna(0)).round(2)

                    def evaluar(f):
                        if f["_merge"] == "left_only": return "❓ Falta reporte chofer"
                        if f["_merge"] == "right_only": return "❓ Sin registro GPS"
                        if abs(f["Dif_Horas"]) > tolerancia: return "⚠️ Alerta diferencia de horas"
                        return "✅ Cuadra OK"

                    df_cruce["Estado_Auditoria"] = df_cruce.apply(evaluar, axis=1)
                    st.dataframe(df_cruce.drop(columns=["_merge"]), use_container_width=True)
                else:
                    st.warning("No se pudo realizar el cruce automático debido al formato de las columnas de fecha/patente.")

        with tab5:
            st.subheader("📥 Descargar Reportes Consolidados")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                if not df_resumen.empty: df_resumen.to_excel(writer, sheet_name="Resumen_Diario", index=False)
                if not df_totales.empty: df_totales.to_excel(writer, sheet_name="Totales_Vehiculo", index=False)
                if not df_detalle.empty: df_detalle.to_excel(writer, sheet_name="Detalle_Tiempos", index=False)
                if archivo_asistencia is not None and 'df_cruce' in locals():
                    df_cruce.to_excel(writer, sheet_name="Auditoria_Cruce", index=False)

            st.download_button(
                label="📥 Descargar Reporte Completo en Excel",
                data=output.getvalue(),
                file_name="Reporte_Flota_Auditado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
else:
    st.info("👆 Por favor, sube tu archivo Excel de GPS en la parte superior para comenzar.")
