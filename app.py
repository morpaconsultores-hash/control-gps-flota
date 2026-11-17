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

st.title("🚛 Sistema Web: Control GPS y Auditoría de Asistencia")
st.markdown(
    "Sube tu archivo de reporte de viaje del GPS. El sistema detectará automáticamente "
    "los encabezados, estructurará los datos por vehículo y te permitirá cruzarlos con la asistencia manual."
)

# --- FUNCIONES AUXILIARES ---
def a_horas(valor):
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
    st.header("⚙️ Configuración")
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
    st.subheader("1️⃣ Archivo del GPS")
    archivo_gps = st.file_uploader("Sube el Excel de Reporte de Viaje", type=["xlsx"], key="gps")

with col2:
    st.subheader("2️⃣ Planilla de Asistencia (Opcional)")
    archivo_asistencia = st.file_uploader("Sube la asistencia manual de choferes", type=["xlsx", "csv"], key="asist")

if archivo_gps is not None:
    try:
        # Leer el archivo sin cabecera fija para analizar su estructura interna
        df_raw = pd.read_excel(archivo_gps, sheet_name=0, header=None)
        
        st.success("✅ ¡Archivo GPS cargado con éxito en la plataforma!")

        # --- PARSER INTELIGENTE DEL REPORTE GPS ---
        registros_totales = []
        vehiculo_actual = "DESCONOCIDO"
        
        for idx, row in df_raw.iterrows():
            val_0 = str(row[0]).strip() if pd.notna(row[0]) else ""
            
            # Detectar nombres de vehículos (patentes en mayúsculas como PCDB55, RBGP67, etc.)
            if len(val_0) >= 5 and len(val_0) <= 8 and not "Período" in val_0 and not "Total" in val_0 and not "Duración" in val_0 and not "Distancia" in val_0 and not "Hora" in val_0:
                vehiculo_actual = val_0
            
            # Detectar filas de eventos que contienen fecha/hora en la columna 0 y 1
            if pd.notna(row[0]) and pd.notna(row[1]) and ("-" in str(row[0]) or "/" in str(row[0])) and not "Hora" in str(row[0]):
                registros_totales.append({
                    "Patente": vehiculo_actual,
                    "Hora Inicio": row[0],
                    "Hora Fin": row[1],
                    "Duración": row[2],
                    "Dirección": row[3],
                    "Movimiento/Espera": row[4]
                })

        df_eventos = pd.DataFrame(registros_totales)

        # Generar Resumen Diario por Patente y Fecha
        if not df_eventos.empty:
            df_eventos["Fecha"] = pd.to_datetime(df_eventos["Hora Inicio"]).dt.strftime("%Y-%m-%d")
            df_eventos["Duracion_Hrs"] = df_eventos["Duración"].apply(a_horas)
            
            df_resumen = df_eventos.groupby(["Fecha", "Patente"], as_index=False).agg({
                "Duracion_Hrs": "sum"
            }).rename(columns={"Duracion_Hrs": "GPS_Activo_Hrs"})
        else:
            df_resumen = pd.DataFrame(columns=["Fecha", "Patente", "GPS_Activo_Hrs"])

        # --- 3. PESTAÑAS DE VISUALIZACIÓN ---
        tab1, tab2, tab3, tab4 = st.tabs([
            "⏱️ Detalle de Tiempos (GPS)", 
            "📊 Resumen por Patente", 
            "🔍 Auditoría con Asistencia",
            "📥 Descargar Reporte"
        ])

        with tab1:
            st.subheader("Detalle Cronológico de Viajes y Esperas")
            if not df_eventos.empty:
                st.dataframe(df_eventos, use_container_width=True)
            else:
                st.warning("No se pudieron extraer los eventos detallados del archivo.")

        with tab2:
            st.subheader("Resumen Diario Consolidado")
            if not df_resumen.empty:
                st.dataframe(df_resumen, use_container_width=True)
            else:
                st.warning("No hay datos para mostrar en el resumen.")

        with tab3:
            st.subheader("Cruce y Auditoría de Horas")
            if archivo_asistencia is None:
                st.info("💡 Sube la **Planilla de Asistencia** de los choferes en el panel superior para activar el cruce automático.")
            else:
                if archivo_asistencia.name.endswith(".csv"):
                    df_asist = pd.read_csv(archivo_asistencia)
                else:
                    df_asist = pd.read_excel(archivo_asistencia)

                # Normalizar columnas
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

                # Cruce por Fecha y Patente
                df_cruce = pd.merge(df_resumen, df_asist, on=["Fecha", "Patente"], how="outer", indicator=True)
                df_cruce["Dif_Horas"] = (df_cruce["Chofer_Neto"].fillna(0) - df_cruce["GPS_Activo_Hrs"].fillna(0)).round(2)

                def evaluar(f):
                    if f["_merge"] == "left_only": return "❓ Falta reporte chofer"
                    if f["_merge"] == "right_only": return "❓ Sin registro GPS"
                    if abs(f["Dif_Horas"]) > tolerancia: return "⚠️ Alerta diferencia de horas"
                    return "✅ Cuadra OK"

                df_cruce["Estado_Auditoria"] = df_cruce.apply(evaluar, axis=1)
                st.dataframe(df_cruce.drop(columns=["_merge"]), use_container_width=True)

        with tab4:
            st.subheader("📥 Exportar Resultados")
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                if not df_eventos.empty: df_eventos.to_excel(writer, sheet_name="Detalle_Eventos", index=False)
                if not df_resumen.empty: df_resumen.to_excel(writer, sheet_name="Resumen_Diario", index=False)
                if archivo_asistencia is not None and 'df_cruce' in locals():
                    df_cruce.to_excel(writer, sheet_name="Auditoria_Cruce", index=False)

            st.download_button(
                label="📥 Descargar Reporte Consolidado (.xlsx)",
                data=output.getvalue(),
                file_name="Auditoria_Flota_GPS.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error procesando el archivo: {e}")
else:
    st.info("👆 Sube tu archivo Excel de GPS en la parte superior para comenzar.")
