import streamlit as st
import pandas as pd
from supabase import create_client, Client
import requests
import json

# --- Configuración Inicial y Conexión ---

# Configuración de página con aspecto profesional
st.set_page_config(
    page_title=st.secrets["app"]["title"],
    layout="wide",
    initial_sidebar_state="expanded"
)

# Conectar a Supabase usando st.secrets (formato TOML)
@st.cache_resource
def init_connection():
    """Inicializa la conexión a Supabase."""
    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["anon_key"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase. Revise 'secrets.toml'. {e}")
        return None

supabase: Client = init_connection()

if not supabase:
    st.stop()

# URL de la Edge Function (evaluar_ofertas_sigsel)
EDGE_FUNCTION_URL = st.secrets["edge_function"]["url"]

# --- Funciones de Datos ---

@st.cache_data(ttl=60)
def fetch_expedientes():
    """Obtiene la lista de expedientes de contratación."""
    try:
        response = supabase.table("expedientes_contratacion").select("id, codigo_proceso, objeto_contrato, estado_fase").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error al cargar expedientes: {e}")
        return pd.DataFrame()

def fetch_ofertas(expediente_id):
    """Obtiene las ofertas para un expediente dado."""
    try:
        response = supabase.table("ofertas_recibidas").select("*").eq("expediente_id", expediente_id).execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"Error al cargar ofertas: {e}")
        return pd.DataFrame()

def call_edge_function(expediente_id):
    """Llama a la Edge Function de Supabase para iniciar el cálculo."""
    headers = {
        "Content-Type": "application/json",
        # Nota: La Edge Function requiere la clave Service Role para escritura. 
        # En un entorno real de Streamlit, se debe usar la clave ANON para la DB, 
        # pero la Edge Function debe tener acceso a la clave Service Role desde su entorno (Deno.env.get).
        # Aquí simplificamos el llamado, confiando en que la Edge Function tiene permisos.
    }
    payload = {"expediente_id": expediente_id}
    
    try:
        response = requests.post(EDGE_FUNCTION_URL, headers=headers, json=payload)
        
        if response.status_code == 200:
            return True, response.json()
        else:
            return False, response.json()
    except Exception as e:
        return False, {"error": str(e)}

# --- Interfaz de Usuario ---

st.title("Sistema SIG-SEL: Módulo de Evaluación Automática")
st.caption("Prototipo Funcional para la Fase de Selección. Eliminando subjetividad en la calificación.")

# --- Sidebar para Selección de Expediente ---
expedientes_df = fetch_expedientes()

with st.sidebar:
    st.header("Selección de Expediente")
    if expedientes_df.empty:
        st.warning("No hay expedientes cargados. Por favor, revise la BD.")
        st.stop()

    # Mapeo para mostrar el código pero usar el ID internamente
    expediente_options = {row['codigo_proceso']: row['id'] for index, row in expedientes_df.iterrows()}
    
    selected_code = st.selectbox(
        "Seleccione el Código del Proceso:",
        options=list(expediente_options.keys()),
        index=0
    )
    
    selected_id = expediente_options[selected_code]
    st.write(f"ID del Expediente (BD): `{selected_id}`")
    
    current_expediente = expedientes_df[expedientes_df['id'] == selected_id].iloc[0]
    st.info(f"Estado: {current_expediente['estado_fase']}")
    st.write(f"Objeto: {current_expediente['objeto_contrato']}")


# --- Main Content ---
st.header(f"Expediente a Evaluar: {selected_code}")

# 1. Obtener Ofertas
ofertas_df = fetch_ofertas(selected_id)

if ofertas_df.empty:
    st.warning("No se han cargado ofertas para este expediente.")
    st.stop()

# 2. Pre-procesamiento de datos para la tabla
columnas_ranking = ['razon_social', 'monto_ofertado', 'puntaje_precio', 'puntaje_tecnico', 'puntaje_total']
display_df = ofertas_df[columnas_ranking].copy()

# Ordenar por puntaje total (descendente)
display_df = display_df.sort_values(by='puntaje_total', ascending=False)
display_df['ranking'] = range(1, len(display_df) + 1)
display_df = display_df[['ranking'] + columnas_ranking]

# Formato de moneda y números
display_df['monto_ofertado'] = display_df['monto_ofertado'].apply(lambda x: f"S/ {x:,.2f}")
display_df['puntaje_precio'] = display_df['puntaje_precio'].round(2)
display_df['puntaje_tecnico'] = display_df['puntaje_tecnico'].round(2)
display_df['puntaje_total'] = display_df['puntaje_total'].round(2)


# 3. Botón de Ejecución del Motor de Cálculo
col1, col2, col3 = st.columns([1, 1, 3])

if col1.button("▶️ Ejecutar Motor de Calificación", type="primary", use_container_width=True):
    with st.spinner("Llamando a la Edge Function... Calculando puntajes de forma objetiva..."):
        success, result = call_edge_function(selected_id)
        
        if success:
            st.success("✅ Cálculo Finalizado con Éxito.")
            st.toast("Puntajes actualizados en la base de datos.")
            # Refrescar los datos de la app para mostrar los nuevos puntajes
            st.cache_data.clear()
            st.rerun()
        else:
            st.error(f"❌ Error en la Ejecución de la Edge Function.")
            st.json(result)

# 4. Visualización Profesional del Ranking
st.subheader("Cuadro Comparativo y Ranking Final (Base 100)")

# Función de estilo para destacar el ganador y el formato
def style_ranking(df):
    """Aplica estilos al DataFrame para hacerlo más profesional y destacar el ganador."""
    styles = []

    # Estilo para el ganador (Ranking 1)
    is_winner = df['ranking'] == 1
    styles.append({
        'selector': '',
        'props': [
            ('background-color', '#e6fff0' if is_winner else '#ffffff'), # Fondo verde suave para el ganador
            ('font-weight', 'bold' if is_winner else 'normal'),
        ]
    })
    
    # Estilo para celdas numéricas (alineación y color)
    styles.append({
        'selector': '.col-puntaje_total, .col-puntaje_precio, .col-puntaje_tecnico',
        'props': [
            ('text-align', 'right'),
        ]
    })
    
    return [
        {'selector': 'th', 'props': [('background-color', '#004d40'), ('color', 'white'), ('font-size', '14px')]}
    ] + [
        {'selector': 'tbody tr:hover', 'props': [('background-color', '#f0f0f0')]},
        {'selector': 'td', 'props': [('font-size', '14px')]}
    ]


st.dataframe(
    display_df.style.apply(lambda x: ['background-color: #e6fff0; font-weight: bold' if x['ranking'] == 1 else '' for i in x], axis=1)
                .set_properties(**{'text-align': 'right'}, subset=['puntaje_precio', 'puntaje_tecnico', 'puntaje_total'])
                .set_table_styles([
                    {'selector': 'th', 'props': [('background-color', '#004d40'), ('color', 'white'), ('font-size', '14px')]},
                    {'selector': 'td', 'props': [('font-size', '14px')]}
                ]),
    use_container_width=True,
    hide_index=True
)

# 5. Conclusiones Rápidas
ganador = display_df.iloc[0]
st.metric(
    label="Ganador (Buena Pro Provisional)", 
    value=ganador['razon_social'], 
    delta=f"Puntaje Total: {ganador['puntaje_total']} / 100", 
    delta_color="normal"
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Requisito Cubierto:** RF-04 (Asistencia a la Evaluación)")
st.sidebar.markdown(f"**Próximo Paso:** Generación Automática de Acta (RF-05)")

# Nota sobre el puntaje técnico (para el usuario)
st.markdown("---")
st.markdown("""
**Nota sobre el Puntaje Técnico:** El puntaje técnico (`puntaje_tecnico`) mostrado ya es el promedio de las calificaciones asignadas por los miembros del Comité (registradas en la tabla `evaluaciones_ofertas`), lo que garantiza la **objetividad** y la **trazabilidad**.
""")