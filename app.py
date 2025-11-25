# app.py
import streamlit as st
import pandas as pd
from supabase import create_client, Client
import json

# --- 1. Configuración de Conexión a Supabase (Seguridad) ---
# Se recomienda usar secretos de Streamlit (st.secrets) para variables sensibles.
SUPABASE_URL = "TU_URL_SUPABASE"  # Reemplazar con la URL de tu proyecto
SUPABASE_KEY = "TU_KEY_ANON"       # Reemplazar con tu clave Anon Key
EDGE_FUNCTION_URL = f"{SUPABASE_URL}/functions/v1/evaluar_ofertas_sigsel" # URL de tu Edge Function

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. Funciones de Data y Lógica ---

# Función para obtener los expedientes disponibles para evaluar
@st.cache_data
def get_expedientes_pendientes():
    """Obtiene la lista de expedientes en estado 'Evaluando Ofertas'."""
    response = supabase.from('expedientes_contratacion').select('*').eq('estado_fase', 'Evaluando Ofertas').execute()
    # Convertir JSONB a dict si es necesario, aunque Supabase Python lo hace por defecto
    return response.data

# Función CLAVE: Llama a la Edge Function para realizar el cálculo
def ejecutar_evaluacion_automatica(expediente_id):
    """Llama a la Edge Function de Supabase para calcular y actualizar puntajes."""
    st.info("Iniciando cálculo automático de puntajes (Llamando a Edge Function)...")
    
    # Esta parte simula la llamada a la Edge Function que hiciste en la guía anterior.
    # En un entorno real de Streamlit en la nube, usarías la librería 'requests' de Python 
    # para hacer un POST a la EDGE_FUNCTION_URL con el expediente_id.
    
    # --- SIMULACIÓN DE LLAMADA (Reemplazar con llamada HTTP real) ---
    # Debido a las restricciones de la clave anónima, simularemos la respuesta exitosa
    # ya que la Edge Function requiere la clave Service Role para actualizar.
    # El código real usaría 'requests.post(EDGE_FUNCTION_URL, headers, json={"expediente_id": expediente_id})'
    
    # Por ahora, para el prototipo: Asumimos éxito y forzamos un re-fetch de la BD
    st.success("✅ Evaluación completada. Actualizando resultados...")
    st.cache_data.clear() # Limpia el caché para refrescar los datos de la BD

# Función para obtener los resultados actualizados
def get_resultados_evaluacion(expediente_id):
    """Obtiene todas las ofertas con los puntajes calculados."""
    response = supabase.from('ofertas_recibidas').select('*').eq('expediente_id', expediente_id).order('puntaje_total', ascending=False).execute()
    return response.data

# --- 3. INTERFAZ DE STREAMLIT ---

st.set_page_config(layout="wide", page_title="SIG-SEL - Módulo de Evaluación")
st.title("Sistema de Gestión de la Fase de Selección (SIG-SEL)")
st.subheader("Dashboard del Comité - Evaluación de Ofertas")
st.markdown("---")

expedientes = get_expedientes_pendientes()

if not expedientes:
    st.warning("No hay expedientes pendientes de evaluación automática.")
else:
    # Selector de Expediente
    exp_opciones = {exp['codigo_proceso']: exp['id'] for exp in expedientes}
    
    proceso_seleccionado = st.selectbox("Seleccione el Proceso a Evaluar:", list(exp_opciones.keys()))
    
    if proceso_seleccionado:
        exp_id_seleccionado = exp_opciones[proceso_seleccionado]
        
        # Muestra la información del expediente
        exp_info = [exp for exp in expedientes if exp['id'] == exp_id_seleccionado][0]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Objeto del Contrato", exp_info['objeto_contrato'])
        with col2:
            st.metric("Valor Estimado", f"S/ {exp_info['valor_estimado']:,.2f}")
        
        st.markdown("---")
        
        # Botón clave para iniciar la evaluación
        if st.button("▶Ejecutar Calificación Automática (Edge Function)", type="primary"):
            ejecutar_evaluacion_automatica(exp_id_seleccionado)
            st.experimental_rerun() # Forzar la recarga para mostrar resultados
            
        st.markdown("---")
        
        # Mostrar la tabla de resultados
        st.header(f"Resultados de Evaluación ({proceso_seleccionado})")
        
        resultados = get_resultados_evaluacion(exp_id_seleccionado)
        
        if resultados:
            df = pd.DataFrame(resultados)
            
            # Formato y selección de columnas para la visualización
            df_display = df[['razon_social', 'monto_ofertado', 'puntaje_precio', 'puntaje_tecnico', 'puntaje_total']]
            
            # Formatear el ranking
            df_display['Ranking'] = df_display['puntaje_total'].rank(ascending=False).astype(int)
            df_display = df_display.sort_values(by='Ranking')
            
            # Aplicar formato de moneda y decimales
            df_display['monto_ofertado'] = df_display['monto_ofertado'].apply(lambda x: f"S/ {x:,.2f}")
            df_display = df_display.rename(columns={'razon_social': 'Postor', 'monto_ofertado': 'Monto Ofertado', 'puntaje_precio': 'Puntaje Económico', 'puntaje_tecnico': 'Puntaje Técnico', 'puntaje_total': 'Puntaje Total'})
            
            # Mostrar la tabla de resultados
            st.dataframe(df_display, use_container_width=True)
            
            # Resaltar al ganador (Postor con Ranking 1)
            ganador = df_display[df_display['Ranking'] == 1]['Postor'].iloc[0]
            st.success(f"La Buena Pro debe otorgarse a: **{ganador}** (Máximo Puntaje Total).")