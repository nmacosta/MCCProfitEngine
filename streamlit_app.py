import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from fpdf import FPDF
import io

# Configuración de la página
st.set_page_config(page_title="Simulador LTV Clínica Particular", layout="wide")

st.title("Simulador de Rentabilidad: Clínica 100% Particular")
st.markdown("Ajusta las variables operativas y comerciales en la barra lateral para evaluar el impacto en el flujo de caja y punto de equilibrio.")

# ==========================================
# BARRA LATERAL: ENTRADA DE DATOS
# ==========================================
st.sidebar.header("1. Capacidad Física")
dias_habiles = st.sidebar.number_input("Días hábiles por mes", min_value=1, max_value=31, value=24)
horas_dia = st.sidebar.number_input("Horas operativas por día", min_value=1, max_value=24, value=10)
num_consultorios = st.sidebar.number_input("Consultorios disponibles", min_value=1, value=3)
duracion_min = st.sidebar.number_input("Duración de consulta (min)", min_value=10, max_value=120, value=20)

st.sidebar.header("2. Demanda Esperada")
ocupacion_pct = st.sidebar.slider("Ocupación de agenda (%)", 0, 100, 30) / 100.0
no_show_pct = st.sidebar.slider("Tasa de Ausentismo (No-show %)", 0, 100, 15) / 100.0
tasa_cs = st.sidebar.slider("Tasa de Cross-Selling (%)", 0, 100, 20) / 100.0

st.sidebar.header("3. Costos y Servicios Auxiliares")
CF = st.sidebar.number_input("Costos Fijos Mensuales ($)", min_value=0, value=3000)
CV = st.sidebar.number_input("Costo Variable x Consulta ($)", min_value=0.0, value=2.0)
precio_cs = st.sidebar.number_input("Ticket Promedio Cross-Selling ($)", min_value=0, value=25)
costo_cs = st.sidebar.number_input("Costo Variable Cross-Selling ($)", min_value=0, value=8)

st.sidebar.header("4. Modelo de Compensación Médica")
esquema = st.sidebar.selectbox(
    "Seleccione el Esquema",
    ("Esquema A: % por Consulta", 
     "Esquema A: Monto Fijo por Consulta", 
     "Esquema B: Fee de Uso (Peaje)", 
     "Esquema C1: Sueldo Fijo al Médico",
     "Esquema C2: Alquiler de Consultorio")
)

# Variables dinámicas según esquema
P = 0.0
r = 0.0
M_d = 0.0
F_c = 0.0
S_m = 0.0
A_m = 0.0

if esquema in ["Esquema A: % por Consulta", "Esquema A: Monto Fijo por Consulta", "Esquema C1: Sueldo Fijo al Médico"]:
    P = st.sidebar.number_input("Precio pagado por paciente (Ticket $)", min_value=0.0, value=40.0)

if esquema == "Esquema A: % por Consulta":
    r = st.sidebar.slider("Porcentaje para el Médico (%)", 0, 100, 50) / 100.0
elif esquema == "Esquema A: Monto Fijo por Consulta":
    M_d = st.sidebar.number_input("Monto Fijo pagado al Médico ($)", min_value=0.0, value=15.0)
elif esquema == "Esquema B: Fee de Uso (Peaje)":
    F_c = st.sidebar.number_input("Fee pagado a la Clínica por paciente ($)", min_value=0.0, value=10.0)
elif esquema == "Esquema C1: Sueldo Fijo al Médico":
    S_m = st.sidebar.number_input("Sueldo Fijo Mensual Total Médicos ($)", min_value=0.0, value=2000.0)
elif esquema == "Esquema C2: Alquiler de Consultorio":
    A_m = st.sidebar.number_input("Alquiler Mensual Total Cobrado ($)", min_value=0.0, value=1500.0)
    st.sidebar.info("En alquiler puro, se asume CV = 0 para la consulta base (el médico pone sus insumos).")

# ==========================================
# MOTOR MATEMÁTICO
# ==========================================
# 1. Cálculos de Capacidad y Volumen
capacidad_max_mensual = dias_habiles * horas_dia * num_consultorios * (60 / duracion_min)
volumen_real = capacidad_max_mensual * ocupacion_pct * (1 - no_show_pct)

# 2. Margen de Cross-Selling (Aplica a todos, asumiendo servicios son de la clínica)
MC_cs = tasa_cs * (precio_cs - costo_cs)

# 3. Lógica Condicional de Esquemas
MC = 0.0
PE = 0.0
utilidad = 0.0
ingresos_totales = 0.0

if esquema == "Esquema A: % por Consulta":
    MC = (P * (1 - r)) - CV + MC_cs
    PE = CF / MC if MC > 0 else float('inf')
    ingresos_totales = (volumen_real * P) + (volumen_real * tasa_cs * precio_cs)
    utilidad = (volumen_real * MC) - CF

elif esquema == "Esquema A: Monto Fijo por Consulta":
    MC = P - M_d - CV + MC_cs
    PE = CF / MC if MC > 0 else float('inf')
    ingresos_totales = (volumen_real * P) + (volumen_real * tasa_cs * precio_cs)
    utilidad = (volumen_real * MC) - CF

elif esquema == "Esquema B: Fee de Uso (Peaje)":
    MC = F_c - CV + MC_cs
    PE = CF / MC if MC > 0 else float('inf')
    ingresos_totales = (volumen_real * F_c) + (volumen_real * tasa_cs * precio_cs)
    utilidad = (volumen_real * MC) - CF

elif esquema == "Esquema C1: Sueldo Fijo al Médico":
    MC = P - CV + MC_cs
    PE = (CF + S_m) / MC if MC > 0 else float('inf')
    ingresos_totales = (volumen_real * P) + (volumen_real * tasa_cs * precio_cs)
    utilidad = (volumen_real * MC) - (CF + S_m)

elif esquema == "Esquema C2: Alquiler de Consultorio":
    MC = MC_cs # Solo gana por el cross-selling sobre esos pacientes
    if (CF - A_m) > 0:
        PE = (CF - A_m) / MC if MC > 0 else float('inf')
    else:
        PE = 0 # El alquiler ya cubre los costos fijos
    ingresos_totales = A_m + (volumen_real * tasa_cs * precio_cs)
    utilidad = A_m - CF + (volumen_real * MC)

margen_operativo = (utilidad / ingresos_totales * 100) if ingresos_totales > 0 else 0

# ==========================================
# DASHBOARD / RENDERIZADO
# ==========================================
if MC <= 0 and esquema != "Esquema C2: Alquiler de Consultorio":
    st.error("⚠️ El Margen de Contribución es negativo o cero. La clínica pierde dinero con cada paciente. Ajusta precios o costos.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Capacidad Máxima (pac/mes)", f"{int(capacidad_max_mensual)}")
col2.metric("Volumen Real (pac/mes)", f"{int(volumen_real)}")
col3.metric("Margen Unitario", f"${MC:,.2f}")
col4.metric("Pto. Equilibrio (pac/mes)", f"{int(PE) if PE != float('inf') else 'Inalcanzable'}")

st.markdown("---")

colA, colB, colC = st.columns(3)
colA.metric("Ingresos Brutos Estimados", f"${ingresos_totales:,.2f}")
colB.metric("EBITDA (Utilidad Neta)", f"${utilidad:,.2f}")
colC.metric("Margen Operativo", f"{margen_operativo:,.1f}%")

st.markdown("---")
st.subheader("Análisis de Sensibilidad: Ocupación vs EBITDA")

# Generar datos para la gráfica variando la ocupación de 0% a 100%
escenarios = []
for oc in range(0, 105, 5):
    vol = capacidad_max_mensual * (oc / 100.0) * (1 - no_show_pct)
    
    if esquema == "Esquema A: % por Consulta":
        u = (vol * MC) - CF
    elif esquema == "Esquema A: Monto Fijo por Consulta":
        u = (vol * MC) - CF
    elif esquema == "Esquema B: Fee de Uso (Peaje)":
        u = (vol * MC) - CF
    elif esquema == "Esquema C1: Sueldo Fijo al Médico":
        u = (vol * MC) - (CF + S_m)
    elif esquema == "Esquema C2: Alquiler de Consultorio":
        u = A_m - CF + (vol * MC)
        
    escenarios.append({"Ocupación (%)": oc, "EBITDA ($)": u})

df_sens = pd.DataFrame(escenarios)

fig = px.line(df_sens, x="Ocupación (%)", y="EBITDA ($)", 
              title=f"Proyección de Utilidad según Ocupación (Ceteris Paribus)",
              markers=True)
fig.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="Punto de Equilibrio Financiero")
fig.add_vline(x=ocupacion_pct*100, line_dash="dot", line_color="green", annotation_text="Ocupación Actual Seleccionada")
fig.update_layout(height=400)

st.plotly_chart(fig, use_container_width=True)

st.markdown("---")
st.subheader("📄 Exportar Escenario")
st.write("Genera un reporte ejecutivo en PDF con los parámetros y resultados actuales.")

# 1. Definir la clase constructora del PDF
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Reporte de Simulacion - MCC Profit Engine', border=False, ln=1, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

# 2. Función para compilar los datos y construir el documento
def generar_pdf():
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    
    # Sección 1: Parámetros Operativos
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "1. Parametros Operativos y de Demanda", ln=1)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"Dias habiles por mes: {dias_habiles}", ln=1)
    pdf.cell(0, 8, f"Horas operativas por dia: {horas_dia}", ln=1)
    pdf.cell(0, 8, f"Consultorios disponibles: {num_consultorios}", ln=1)
    pdf.cell(0, 8, f"Duracion de consulta: {duracion_min} min", ln=1)
    pdf.cell(0, 8, f"Ocupacion de agenda proyectada: {ocupacion_pct*100}%", ln=1)
    pdf.cell(0, 8, f"Tasa de Ausentismo (No-show): {no_show_pct*100}%", ln=1)
    pdf.cell(0, 8, f"Tasa de Cross-Selling: {tasa_cs*100}%", ln=1)
    pdf.ln(5)
    
    # Sección 2: Estructura Financiera
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "2. Estructura de Costos y Precios", ln=1)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"Costos Fijos Mensuales: ${CF:,.2f}", ln=1)
    pdf.cell(0, 8, f"Costo Variable por Consulta: ${CV:,.2f}", ln=1)
    pdf.cell(0, 8, f"Ticket Promedio Cross-Selling: ${precio_cs:,.2f}", ln=1)
    pdf.cell(0, 8, f"Esquema Medico Seleccionado: {esquema}", ln=1)
    pdf.ln(5)
    
    # Sección 3: Resultados Proyectados
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "3. Resultados Financieros del Escenario", ln=1)
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"Capacidad Maxima: {int(capacidad_max_mensual)} pac/mes", ln=1)
    pdf.cell(0, 8, f"Volumen Real Estimado: {int(volumen_real)} pac/mes", ln=1)
    pdf.cell(0, 8, f"Margen de Contribucion Unitario: ${MC:,.2f}", ln=1)
    
    texto_pe = f"{int(PE)} pac/mes" if PE != float('inf') else "Inalcanzable"
    pdf.cell(0, 8, f"Punto de Equilibrio: {texto_pe}", ln=1)
    
    pdf.cell(0, 8, f"Ingresos Brutos Estimados: ${ingresos_totales:,.2f}", ln=1)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 8, f"EBITDA (Utilidad Neta): ${utilidad:,.2f}", ln=1)
    pdf.cell(0, 8, f"Margen Operativo: {margen_operativo:,.1f}%", ln=1)
    
    # Convertir el PDF a bytes para Streamlit
    return bytes(pdf.output(dest='S'))

# 3. Renderizar el botón de descarga
pdf_bytes = generar_pdf()

st.download_button(
    label="📥 Descargar Informe Ejecutivo (PDF)",
    data=pdf_bytes,
    file_name="Reporte_Simulacion_Clinica.pdf",
    mime="application/pdf",
    type="primary"
)
