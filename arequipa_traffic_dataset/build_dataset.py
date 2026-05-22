#!/usr/bin/env python3
import os
import sys
import sqlite3
import numpy as np
import pandas as pd

DB_PATH = "data/traffic_records.db"
METADATA_PATH = "data/segment_metadata.csv"
ADJ_PATH = "data/adjacency_matrix.npy"
OUTPUT_PATH = "data/arequipa_traffic.npz"

def main():
    print("=== Iniciando Ensamblado del Dataset para GNN ===")
    
    # 1. Verificar archivos requeridos
    if not os.path.exists(DB_PATH):
        print(f"Error: No se encuentra la base de datos de trafico en '{DB_PATH}'.")
        print("ejecutar antes 'collect_traffic.py' para recolectar datos.")
        sys.exit(1)
        
    if not os.path.exists(METADATA_PATH) or not os.path.exists(ADJ_PATH):
        print("Error: No se encuentran los archivos del grafo ('segment_metadata.csv' o 'adjacency_matrix.npy').")
        print("ejecutar primero 'extract_network.py'.")
        sys.exit(1)
        
    df_nodes = pd.read_csv(METADATA_PATH)
    node_ids = sorted(df_nodes['node_id'].tolist())
    N = len(node_ids)
    print(f"Grafo cargado: {N} nodos (segmentos viales).")
    
    # Cargar Matriz de Adyacencia
    adj_matrix = np.load(ADJ_PATH)
    print(f"Matriz de adyacencia cargada. Shape: {adj_matrix.shape}")
    
    conn = sqlite3.connect(DB_PATH)
    df_traffic = pd.read_sql_query("SELECT * FROM traffic_data", conn)
    conn.close()
    
    if len(df_traffic) == 0:
        print("Error: La base de datos está vacía. No hay lecturas de tráfico recolectadas.")
        sys.exit(1)
        
    print(f"Se cargaron {len(df_traffic)} lecturas individuales de tráfico.")
    
    df_traffic['timestamp'] = pd.to_datetime(df_traffic['timestamp'])
    
    unique_timestamps = sorted(df_traffic['timestamp'].unique())
    T = len(unique_timestamps)
    print(f"Total de intervalos de tiempo únicos (T): {T}")
    
    if T < 2:
        print("Advertencia: Se necesitan al menos 2 intervalos de tiempo para entrenar un modelo temporal.")
        print("Recolecta más datos antes de entrenar un modelo final.")
        
    F = 2
    X = np.zeros((T, N, F))
    
    node_to_idx = {node_id: idx for idx, node_id in enumerate(node_ids)}
    
    print("Pivoteando y alineando datos temporales...")
    
    df_pivot_speed = df_traffic.pivot(index='timestamp', columns='node_id', values='current_speed')
    df_pivot_free = df_traffic.pivot(index='timestamp', columns='node_id', values='free_flow_speed')
    
    df_pivot_speed = df_pivot_speed.interpolate(method='time', limit_direction='both')
    df_pivot_free = df_pivot_free.interpolate(method='time', limit_direction='both')
    
    for node_id in node_ids:
        if node_id not in df_pivot_speed.columns:
            df_pivot_speed[node_id] = 40.0
            df_pivot_free[node_id] = 50.0
        else:
            mean_speed = df_pivot_speed[node_id].mean()
            mean_free = df_pivot_free[node_id].mean()
            if pd.isna(mean_speed):
                mean_speed = 40.0
            if pd.isna(mean_free):
                mean_free = 50.0
            df_pivot_speed[node_id] = df_pivot_speed[node_id].fillna(mean_speed)
            df_pivot_free[node_id] = df_pivot_free[node_id].fillna(mean_free)
            
    # Llenar el tensor X
    for t_idx, ts in enumerate(unique_timestamps):
        for node_id in node_ids:
            n_idx = node_to_idx[node_id]
            X[t_idx, n_idx, 0] = df_pivot_speed.at[ts, node_id]
            X[t_idx, n_idx, 1] = df_pivot_free.at[ts, node_id]
            
    print(f"Tensor X construido. Shape: {X.shape} (TimeSteps={T}, Nodes={N}, Features={F})")
    
    np.savez_compressed(
        OUTPUT_PATH,
        x=X,
        adj=adj_matrix,
        timestamps=np.array([ts.isoformat() for ts in unique_timestamps], dtype=object)
    )
    
    print(f"Dataset final guardado en: {OUTPUT_PATH}")
    
    avg_speed = np.mean(X[:, :, 0])
    avg_free_flow = np.mean(X[:, :, 1])
    print("\n--- Estadísticas del Dataset ---")
    print(f"Rango de fechas: {unique_timestamps[0]} a {unique_timestamps[-1]}")
    print(f"Velocidad promedio general: {avg_speed:.2f} km/h")
    print(f"Velocidad de flujo libre promedio: {avg_free_flow:.2f} km/h")
    print(f"Nivel de congestión promedio (Velocidad / Flujo Libre): {(avg_speed/avg_free_flow)*100:.1f}%")
    print("================================================")

if __name__ == "__main__":
    main()
