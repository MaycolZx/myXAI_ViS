#!/usr/bin/env python3
import os
import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "data/traffic_records.db"

def main():
    print("=== Generando Datos Simulados de Trafico ===")
    os.makedirs("data", exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Asegurar que la tabla exista
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
    
    # 25 nodos (0 a 24)
    nodes = list(range(25))
    
    start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
    
    records_inserted = 0
    
    for i in range(12):
        timestamp = (start_time + timedelta(minutes=10 * i)).isoformat()
        
        # Simular velocidad promedio de la ciudad con variaciones de hora pico
        # A las 8:30 y 8:40 AM (i = 3, 4)
        if i in [3, 4, 5]:
            base_speed_factor = 0.65  # Hora pico (velocidades mas lentas)
        else:
            base_speed_factor = 0.85  # Trafico fluido
            
        for node_id in nodes:
            if node_id in [0, 1, 8]:
                free_flow = 80.0
            elif node_id in [2, 3, 4, 5, 17, 22]: # Avenidas primarias
                free_flow = 60.0
            else: # Avenidas secundarias
                free_flow = 40.0
                
            # Velocidad actual con ruido aleatorio
            speed_deviation = random.uniform(-5.0, 5.0)
            current = max(10.0, (free_flow * base_speed_factor) + speed_deviation)
            
            # Limitar para que no supere el free flow de manera absurda
            current = min(current, free_flow + 5.0)
            
            # Tiempos de viaje en segundos (asumiendo tramos de 1000m)
            free_flow_time = (1.0 / (free_flow / 3.6)) * 1000.0  # en segundos
            current_time = (1.0 / (current / 3.6)) * 1000.0
            
            confidence = random.uniform(0.85, 0.99)
            
            cursor.execute("""
                INSERT OR REPLACE INTO traffic_data 
                (timestamp, node_id, current_speed, free_flow_speed, current_travel_time, free_flow_travel_time, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp,
                node_id,
                round(current, 2),
                round(free_flow, 2),
                round(current_time, 1),
                round(free_flow_time, 1),
                round(confidence, 2)
            ))
            records_inserted += 1
            
    conn.commit()
    conn.close()
    
    print(f"Se han insertado {records_inserted} registros simulados de trafico.")
    print(f"Base de datos poblada en: {DB_PATH}")

if __name__ == "__main__":
    main()
