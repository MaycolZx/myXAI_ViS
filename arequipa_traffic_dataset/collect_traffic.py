#!/usr/bin/env python3
import os
import sys
import time
import sqlite3
import argparse
import pandas as pd
from datetime import datetime
import requests

DB_PATH = "data/traffic_records.db"
METADATA_PATH = "data/segment_metadata.csv"

def init_db():
    """Initializes the SQLite database if it doesn't exist."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS traffic_data (
            timestamp TEXT NOT NULL,
            node_id INTEGER NOT NULL,
            current_speed REAL,
            free_flow_speed REAL,
            current_travel_time REAL,
            free_flow_travel_time REAL,
            confidence REAL,
            PRIMARY KEY (timestamp, node_id)
        );
    """)
    conn.commit()
    conn.close()

def load_segments():
    if not os.path.exists(METADATA_PATH):
        print(f"Error: No se encontro el archivo de metadata en '{METADATA_PATH}'.")
        print("Ejecutar primero 'extract_network.py'.")
        sys.exit(1)
        
    return pd.read_csv(METADATA_PATH)

def fetch_traffic_data(lat, lon, api_key):
    # TomTom Flow Segment Data Endpoint
    url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
    params = {
        'point': f"{lat},{lon}",
        'key': api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if 'flowSegmentData' in data:
                flow = data['flowSegmentData']
                return {
                    'current_speed': flow.get('currentSpeed'),
                    'free_flow_speed': flow.get('freeFlowSpeed'),
                    'current_travel_time': flow.get('currentTravelTime'),
                    'free_flow_travel_time': flow.get('freeFlowTravelTime'),
                    'confidence': flow.get('confidence')
                }
            else:
                print(f"Advertencia: Respuesta de TomTom no contiene 'flowSegmentData' para {lat},{lon}")
        elif response.status_code == 403:
            print("Error 403: API Key inválida o límite de cuota superado.")
        else:
            print(f"Error en API TomTom (Codigo {response.status_code}) para {lat},{lon}")
    except Exception as e:
        print(f"Error de conexion para {lat},{lon}: {e}")
        
    return None

def collect_once(df_segments, api_key):
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] Iniciando ronda de recoleccion para {len(df_segments)} segmentos...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    success_count = 0
    for _, row in df_segments.iterrows():
        node_id = int(row['node_id'])
        lat = row['mid_lat']
        lon = row['mid_lon']
        
        # Consultar API
        res = fetch_traffic_data(lat, lon, api_key)
        
        if res:
            cursor.execute("""
                INSERT OR REPLACE INTO traffic_data 
                (timestamp, node_id, current_speed, free_flow_speed, current_travel_time, free_flow_travel_time, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                node_id,
                res['current_speed'],
                res['free_flow_speed'],
                res['current_travel_time'],
                res['free_flow_travel_time'],
                res['confidence']
            ))
            success_count += 1
        
        # Dormir 0.25 segundos para respetar el límite de 5 QPS del plan gratuito
        time.sleep(0.25)
        
    conn.commit()
    conn.close()
    print(f"[{datetime.now().isoformat()}] Ronda completada. Éxito: {success_count}/{len(df_segments)} segmentos.")

def main():
    parser = argparse.ArgumentParser(description="Recolector de datos de tráfico usando la API de TomTom.")
    parser.add_argument("--api-key", help="Clave de API de desarrollador de TomTom (o setea la variable TOMTOM_API_KEY)")
    parser.add_argument("--interval", type=int, default=10, help="Intervalo de recolección en minutos (defecto: 10)")
    parser.add_argument("--once", action="store_true", help="Ejecutar una sola ronda de recolección y salir")
    
    args = parser.parse_args()
    
    # Obtener API Key
    api_key = args.api_key or os.environ.get("TOMTOM_API_KEY")
    if not api_key:
        print("Error: No se especifico la API Key de TomTom.")
        print("Puedes pasarla con --api-key o definir la variable de entorno TOMTOM_API_KEY.")
        sys.exit(1)
        
    # Inicializar Base de Datos y cargar segmentos
    init_db()
    df_segments = load_segments()
    
    if args.once:
        collect_once(df_segments, api_key)
    else:
        print(f"Iniciando servicio de recoleccion continua. Intervalo: {args.interval} minutos.")
        print("Presiona Ctrl+C para detener.")
        try:
            while True:
                start_time = time.time()
                collect_once(df_segments, api_key)
                
                # Calcular tiempo a dormir hasta el siguiente intervalo
                elapsed = time.time() - start_time
                sleep_time = max(0, (args.interval * 60) - elapsed)
                
                if sleep_time > 0:
                    print(f"Durmiendo {sleep_time/60:.2f} minutos hasta la siguiente ronda...")
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            print("\nServicio de recolección detenido por el usuario.")

if __name__ == "__main__":
    main()
