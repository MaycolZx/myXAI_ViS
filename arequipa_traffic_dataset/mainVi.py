import sqlite3
from folium.plugins import HeatMapWithTime
import pandas as pd
import folium
import matplotlib.pyplot as plt

DB_PATH = "data/traffic_records.db"
METADATA_PATH = "data/segment_metadata.csv"


def plot_heatmap_with_timeline():
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT timestamp, node_id, current_speed, free_flow_speed
        FROM traffic_data
        ORDER BY timestamp ASC
    """
    df_traffic = pd.read_sql_query(query, conn)
    conn.close()

    if df_traffic.empty:
        print("No hay suficientes datos para crear el mapa de calor.")
        return

    df_meta = pd.read_csv(METADATA_PATH)
    df_map = pd.merge(df_meta, df_traffic, on="node_id", how="inner")

    df_map['free_flow_speed'] = df_map['free_flow_speed'].replace(0, 1)
    df_map['weight'] = 1.0 - (df_map['current_speed'] / df_map['free_flow_speed'])
    
    df_map['weight'] = df_map['weight'].apply(lambda x: max(0.0, x))

    df_map['timestamp_dt'] = pd.to_datetime(df_map['timestamp'], format='ISO8601')
    
    time_steps = df_map['timestamp_dt'].sort_values().unique()
    
    heat_data = []
    time_index = []
    
    for t in time_steps:
        df_t = df_map[df_map['timestamp_dt'] == t]
        
        puntos = df_t[['mid_lat', 'mid_lon', 'weight']].values.tolist()
        heat_data.append(puntos)
        
        hora_legible = pd.to_datetime(t).strftime('%Y-%m-%d %H:%M')
        time_index.append(hora_legible)

    centro_lat = df_map['mid_lat'].mean()
    centro_lon = df_map['mid_lon'].mean()
    mapa_calor = folium.Map(location=[centro_lat, centro_lon], zoom_start=13, tiles="CartoDB dark_matter")

    HeatMapWithTime(
        heat_data,
        index=time_index,
        auto_play=True,
        radius=60,
        max_opacity=0.8,
        gradient={0.2: 'blue', 0.4: 'lime', 0.6: 'yellow', 1.0: 'red'}
    ).add_to(mapa_calor)

    mapa_calor.save("mapa_calor_tiempo.html")
    print("¡Mapa animado guardado como 'mapa_calor_tiempo.html'!")

def plot_traffic_map():
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT node_id, current_speed, free_flow_speed, timestamp
        FROM traffic_data
        WHERE timestamp = (SELECT MAX(timestamp) FROM traffic_data)
    """
    df_traffic = pd.read_sql_query(query, conn)
    conn.close()

    df_meta = pd.read_csv(METADATA_PATH)
    df_map = pd.merge(df_meta, df_traffic, on="node_id", how="inner")

    if df_map.empty:
        print("No hay datos para mapear.")
        return

    centro_lat = df_map['mid_lat'].mean()
    centro_lon = df_map['mid_lon'].mean()
    mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=13, tiles="CartoDB positron")

    for _, row in df_map.iterrows():
        if row['free_flow_speed'] > 0:
            ratio = row['current_speed'] / row['free_flow_speed']
        else:
            ratio = 1.0 

        if ratio > 0.75:
            color = 'green'
        elif ratio > 0.50:
            color = 'orange'
        else:
            color = 'red'

        popup_info = (f"<b>ID:</b> {row['node_id']}<br>"
                      f"<b>Vel. Actual:</b> {row['current_speed']} km/h<br>"
                      f"<b>Vel. Normal:</b> {row['free_flow_speed']} km/h<br>"
                      f"<b>Ultima act:</b> {row['timestamp'][11:16]}")

        folium.CircleMarker(
            location=[row['mid_lat'], row['mid_lon']],
            radius=6,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.8,
            popup=folium.Popup(popup_info, max_width=200)
        ).add_to(mapa)

    mapa.save("mapa_trafico.html")

def plot_speed_trend(node_id_to_plot):
    conn = sqlite3.connect(DB_PATH)
    query = f"""
        SELECT timestamp, current_speed, free_flow_speed 
        FROM traffic_data 
        WHERE node_id = {node_id_to_plot} 
        ORDER BY timestamp
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    if df.empty:
        print(f"No se encontraron datos historicos para el nodo {node_id_to_plot}.")
        return

    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601')
    
    plt.figure(figsize=(10, 5))
    
    plt.plot(df['timestamp'], df['current_speed'], label='Velocidad Actual', color='red', marker='o', markersize=4)
    
    plt.plot(df['timestamp'], df['free_flow_speed'], label='Flujo Libre (Límite)', color='green', linestyle='--')
    
    plt.title(f'Tendencia de Trafico - Segmento {node_id_to_plot}')
    plt.xlabel('Hora de recoleccion')
    plt.ylabel('Velocidad (km/h)')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.7)
    
    plt.gcf().autofmt_xdate()
    
    plt.tight_layout()
    plt.savefig(f"tendencia_nodo_{node_id_to_plot}.png")
    print(f"Guardado como 'tendencia_nodo_{node_id_to_plot}.png'")
    plt.show()

if __name__ == "__main__":
    plot_traffic_map()

    plot_heatmap_with_timeline()
    
    plot_speed_trend(node_id_to_plot=1)
