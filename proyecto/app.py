import streamlit as st          # (LIBRERÍA) Framework para crear aplicaciones web interactivas
import pandas as pd             # (LIBRERÍA) Manipulación y análisis de datos
import pydeck as pdk            # (LIBRERÍA) Visualización geoespacial 3D basada en deck.gl
import time                     # (MÓDULO) Para pausar la ejecución (delay en animación)
import requests                 # (LIBRERÍA) Para hacer solicitudes HTTP (consultar OSRM)
import numpy as np              # (LIBRERÍA) Funciones matemáticas (compatibilidad general)

# ======================================================
# CONFIGURACIÓN DE STREAMLIT (st.set_page_config)
# ======================================================
st.set_page_config(
    page_title="Movilidad CR",   # Título de la pestaña del navegador
    page_icon="🚍",              # Ícono
    layout="wide"                # Distribución amplia de la página
)

# ======================================================
# CARGA DE DATOS (pandas.read_excel)
# ======================================================
@st.cache_data
def load_data():
    """
    Función: load_data()
    Uso: Carga el archivo Excel utilizando pandas.read_excel()
    Decorador: @st.cache_data → Streamlit almacena los datos en caché para no recargar cada vez.
    """
    return pd.read_excel("datos/rutas_cr.xlsx")

# DataFrame con los datos principales
df = load_data()

# Crea una nueva columna calculada usando operaciones directas de pandas
df["eficiencia"] = df["pasajeros_prom"] / df["distancia_km"]

# ======================================================
# FUNCIÓN DE RUTA REAL (OSRM API REQUEST)
# ======================================================
def obtener_ruta_osrm(lat1, lon1, lat2, lon2):
    """
    Función: obtener_ruta_osrm()
    · Usa: requests.get() para consultar la API pública OSRM.
    · Parámetros: lat/lon iniciales y finales.
    · Respuesta: GeoJSON → Se extraen coordenadas y duración desde el JSON.
    · Devuelve: DataFrame con puntos de la ruta + tiempo estimado.
    """
    
    # Construcción de URL siguiendo el formato OSRM /route/v1/driving
    url = (
        f"https://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    )

    r = requests.get(url)   # Petición GET a OSRM

    # Validación de respuesta HTTP
    if r.status_code != 200:
        return pd.DataFrame(), None

    try:
        data = r.json()  # Convierte la respuesta en JSON

        # Extrae geometría del objeto GeoJSON
        coords = data["routes"][0]["geometry"]["coordinates"]

        # Extrae tiempo (segundos → minutos)
        duracion = data["routes"][0]["duration"] / 60

    except Exception:
        return pd.DataFrame(), None

    # Convierte cada punto (lon,lat) → (lat,lon)
    ruta = [{"lat": c[1], "lon": c[0]} for c in coords]

    return pd.DataFrame(ruta), duracion

# ======================================================
# ICONO PARA PYDECK (IconLayer)
# ======================================================
icon_bus = {
    "url": "https://cdn-icons-png.flaticon.com/512/61/61088.png",  # Ícono PNG en línea
    "width": 512,           # Tamaño original
    "height": 512,
    "anchorY": 512          # Valor para centrar el icono en PyDeck
}

# ======================================================
# ENCABEZADO PRINCIPAL DEL DASHBOARD
# ======================================================
st.title(" Dashboard de Movilidad CR")
st.markdown("Use el panel izquierdo para elegir **origen** y **destino**.")

# ======================================================
# SIDEBAR (st.sidebar + selectbox)
# ======================================================
st.sidebar.header("🔎 Selección de Origen y Destino")

# selectbox() crea listas desplegables para seleccionar origen/destino
origen = st.sidebar.selectbox("Seleccione el origen:", sorted(df["inicio"].unique()))
destino = st.sidebar.selectbox("Seleccione el destino:", sorted(df["fin"].unique()))

# Filtra DataFrame según selección del usuario (operadores lógicos de pandas)
rutas_od = df[(df["inicio"] == origen) & (df["fin"] == destino)]

# Si no hay rutas → se detiene la app
if rutas_od.empty:
    st.error("No existen rutas entre este origen y destino.")
    st.stop()

# Si existen varias rutas, se selecciona una mediante otro selectbox
if len(rutas_od) > 1:
    ruta_seleccionada = st.sidebar.selectbox(
        "Varias rutas disponibles:",
        rutas_od["ruta"].unique()
    )
    fila = rutas_od[rutas_od["ruta"] == ruta_seleccionada].iloc[0]
else:
    fila = rutas_od.iloc[0]

# Extrae coordenadas como variables individuales
lat_inicio, lon_inicio = fila["lat_inicio"], fila["lon_inicio"]
lat_fin, lon_fin = fila["lat_fin"], fila["lon_fin"]

# ======================================================
# RUTA REAL UTILIZANDO obtener_ruta_osrm()
# ======================================================
ruta_real, duracion_min = obtener_ruta_osrm(lat_inicio, lon_inicio, lat_fin, lon_fin)

if ruta_real.empty:
    st.error("Error al obtener ruta desde OSRM.")
    st.stop()

# ======================================================
# INDICADORES (st.metric)
# ======================================================
st.header("📊 Indicadores")

# Crea tres columnas con Streamlit → layout responsivo
col1, col2, col3 = st.columns(3)

# idxmin() / idxmax() → funciones de pandas para seleccionar extremos
ruta_corta = rutas_od.loc[rutas_od["distancia_km"].idxmin()]
col1.metric("Ruta más corta", ruta_corta["ruta"], f"{ruta_corta['distancia_km']} km")

ruta_freq = rutas_od.loc[rutas_od["frecuencia_hora"].idxmax()]
col2.metric("Más frecuente", ruta_freq["ruta"], f"{ruta_freq['frecuencia_hora']} buses/hora")

ruta_eff = rutas_od.loc[rutas_od["eficiencia"].idxmax()]
col3.metric("Más eficiente", ruta_eff["ruta"], f"{ruta_eff['eficiencia']:.1f} pas/km")

# Indicador del tiempo estimado desde OSRM
st.metric("⏱ Duración estimada (OSRM)", f"{duracion_min:.1f} minutos")

# ======================================================
# TABLA CON DATAFRAME (st.dataframe)
# ======================================================
st.header(f"📋 Rutas disponibles entre {origen} → {destino}")
st.dataframe(rutas_od)   # Tabla interactiva nativa de Streamlit

# ======================================================
# GRÁFICO (st.bar_chart)
# ======================================================
st.header("📈 Demanda total por ruta ")
st.bar_chart(df.groupby("ruta")["pasajeros_prom"].sum())  # Visualización rápida

# ======================================================
# DISEÑO DE MAPAS: PyDeck + Folium
# ======================================================
col_mapa, col_minimapa = st.columns([4, 1])

# ---------------------- MAPA PRINCIPAL ----------------------
with col_mapa:
    st.header("🛰️ Simulación del Recorrido Real (OSRM)")
    map_placeholder = st.empty()   # Contenedor para el mapa animado (se actualiza frame por frame)

# ---------------------- MINI-MAPA ---------------------------
with col_minimapa:
    st.header("🗺️ Mapa general")
    st.caption("Vista rápida del sistema completo")

    # Librerías geoespaciales
    import geopandas as gpd            # (LIBRERÍA) Tratamiento de datos geográficos tipo GIS
    from shapely.geometry import LineString  # (FUNCIÓN) Construcción de líneas geográficas
    import folium                       # (LIBRERÍA) Mapas interactivos 2D
    from streamlit_folium import folium_static  # Renderiza mapas Folium en Streamlit

    def construir_gdf_rutas(df):
        """
        Función: construir_gdf_rutas()
        · Usa GeoPandas (gpd.GeoDataFrame)
        · Crea objetos LineString de Shapely para cada ruta
        · Devuelve un GeoDataFrame con geometrías
        """
        geometries = []
        for _, row in df.iterrows():
            geometries.append(LineString([
                (row["lon_inicio"], row["lat_inicio"]),
                (row["lon_fin"], row["lat_fin"])
            ]))
        return gpd.GeoDataFrame(df.copy(), geometry=geometries, crs="EPSG:4326")

    gdf_rutas = construir_gdf_rutas(df)

    # Creación del mapa Folium (folium.Map)
    m = folium.Map(location=[9.93, -84.08], zoom_start=7, width=310, height=380, control_scale=True)

    # Función de color según cuantiles (pandas.quantile)
    def eficiencia_color(value):
        if value > df["eficiencia"].quantile(0.66):
            return "green"
        elif value > df["eficiencia"].quantile(0.33):
            return "orange"
        else:
            return "red"

    # Dibuja rutas en el mapa Folium (folium.PolyLine)
    for _, row in gdf_rutas.iterrows():
        folium.PolyLine(
            locations=[(row["lat_inicio"], row["lon_inicio"]), (row["lat_fin"], row["lon_fin"])],
            color=eficiencia_color(row["eficiencia"]),
            weight=4,
            tooltip=row["ruta"]
        ).add_to(m)

    folium_static(m)   # Renderiza en Streamlit
# ======================================================
# SIMULACIÓN DEL RECORRIDO (PyDeck + bucle for)
# ======================================================
for i in range(len(ruta_real)):
    # Cada iteración dibuja:
    # - Un punto del camino (layer_bus)
    # - La línea recorrida hasta ese momento (layer_path)
    # - Actualiza la cámara (pdk.ViewState)

    punto = ruta_real.iloc[i:i+1]      # Punto actual
    camino = ruta_real.iloc[:i+1]      # Trayecto recorrido hasta el frame actual

    layer_bus = pdk.Layer(
        "IconLayer",
        data=punto.assign(icon=icon_bus),
        get_icon="icon",
        get_size=4,
        size_scale=15,
        get_position='[lon, lat]'
    )

    layer_path = pdk.Layer(
        "PathLayer",
        data=[{"path": camino[["lon", "lat"]].values.tolist()}],
        get_color=[0, 150, 255],
        width_scale=7,
        width_min_pixels=4
    )

    view_state = pdk.ViewState(
        latitude=punto["lat"].iloc[0],
        longitude=punto["lon"].iloc[0],
        zoom=14,
        pitch=50
    )

    deck = pdk.Deck(layers=[layer_path, layer_bus], initial_view_state=view_state)
    map_placeholder.pydeck_chart(deck)

    time.sleep(0.12)
