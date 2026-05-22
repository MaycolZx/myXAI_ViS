#!/usr/bin/env python3
import os
import numpy as np
import pandas as pd
import networkx as nx
import osmnx as ox
from shapely.geometry import LineString

def main():
    print("=== Iniciando Extraccion de Red Vial de Arequipa ===")
    
    ox.settings.use_cache = True
    ox.settings.log_console = False
    
    center_point = (-16.4000, -71.5333)
    radius_meters = 5000
    print(f"Descargando datos viales de OSM para Arequipa urbana (centro: {center_point}, radio: {radius_meters}m)...")
    try:
        G = ox.graph_from_point(center_point, dist=radius_meters, network_type="drive")
        print(f"Grafo original descargado: {len(G.nodes)} nodos y {len(G.edges)} aristas.")
    except Exception as e:
        print(f"Error al descargar la red de OSM: {e}")
        return

    # 3. Filtrar para quedarse solo con vias principales (para optimizar la cuota de TomTom)
    # Categorias principales de carreteras en OSM
    target_highways = {'motorway', 'trunk', 'primary', 'secondary'}
    
    # Filtrar aristas
    print("Filtrando aristas para vías principales (primary, secondary, trunk, motorway)...")
    edges_to_keep = []
    for u, v, k, data in G.edges(keys=True, data=True):
        h_type = data.get('highway', '')
        if isinstance(h_type, list):
            h_type = h_type[0]
        if h_type in target_highways:
            edges_to_keep.append((u, v, k))
            
    # Crear un subgrafo con las aristas filtradas
    G_filtered = G.edge_subgraph(edges_to_keep).copy()
    
    # Eliminar nodos aislados
    isolated = list(nx.isolates(G_filtered))
    G_filtered.remove_nodes_from(isolated)
    print(f"Grafo filtrado: {len(G_filtered.nodes)} nodos y {len(G_filtered.edges)} aristas.")
    
    # Mapearemos cada arista a un id entero (0 a N-1)
    gnn_nodes = []
    node_coords = {node: (data['y'], data['x']) for node, data in G_filtered.nodes(data=True)}
    
    print("Calculando puntos medios de los segmentos de calle...")
    for idx, (u, v, k, data) in enumerate(G_filtered.edges(keys=True, data=True)):
        u_lat, u_lon = node_coords[u]
        v_lat, v_lon = node_coords[v]
        
        # Calcular el punto medio geografico
        if 'geometry' in data and isinstance(data['geometry'], LineString):
            geom = data['geometry']
            midpoint = geom.interpolate(0.5, normalized=True)
            mid_lat, mid_lon = midpoint.y, midpoint.x
        else:
            mid_lat = (u_lat + v_lat) / 2.0
            mid_lon = (u_lon + v_lon) / 2.0
            
        street_name = data.get('name', 'Calle Sin Nombre')
        if isinstance(street_name, list):
            street_name = " / ".join(street_name)
            
        highway_type = data.get('highway', 'unknown')
        if isinstance(highway_type, list):
            highway_type = highway_type[0]
            
        gnn_nodes.append({
            'node_id': idx,
            'osm_u': u,
            'osm_v': v,
            'osm_key': k,
            'name': street_name,
            'length': data.get('length', 0.0),
            'highway': highway_type,
            'mid_lat': mid_lat,
            'mid_lon': mid_lon
        })
        
    df_nodes = pd.DataFrame(gnn_nodes)
    
    # Priorizamos segmentos mas largos o avenidas principales si son demasiados
    MAX_NODES = 25
    if len(df_nodes) > MAX_NODES:
        print(f"El grafo filtrado tiene {len(df_nodes)} segmentos. Limitando a los {MAX_NODES} segmentos más largos para cuidar la cuota de TomTom.")
        df_nodes = df_nodes.sort_values(by='length', ascending=False).head(MAX_NODES).copy()
        # Re-indexar de 0 a MAX_NODES-1
        df_nodes['node_id'] = range(len(df_nodes))
        
    print(f"Total de segmentos (nodos GNN) seleccionados: {len(df_nodes)}")
    print(df_nodes[['node_id', 'name', 'highway', 'length']].head(10))
    
    N = len(df_nodes)
    A = np.zeros((N, N))
    
    print("Calculando matriz de adyacencia ponderada por distancia...")
    
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000.0 # radio de la tierra en metros
        phi1 = np.radians(lat1)
        phi2 = np.radians(lat2)
        dphi = np.radians(lat2 - lat1)
        dlambda = np.radians(lon2 - lon1)
        a = np.sin(dphi/2.0)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2.0)**2
        return 2.0 * R * np.arctan2(np.sqrt(a), np.sqrt(1.0-a))

    distances = []
    
    for i in range(N):
        row_i = df_nodes.iloc[i]
        u_i, v_i = row_i['osm_u'], row_i['osm_v']
        lat_i, lon_i = row_i['mid_lat'], row_i['mid_lon']
        
        for j in range(i + 1, N):
            row_j = df_nodes.iloc[j]
            u_j, v_j = row_j['osm_u'], row_j['osm_v']
            lat_j, lon_j = row_j['mid_lat'], row_j['mid_lon']
            
            # Verificar si comparten interseccion
            shares_intersection = (u_i == u_j) or (u_i == v_j) or (v_i == u_j) or (v_i == v_j)
            
            if shares_intersection:
                dist = haversine(lat_i, lon_i, lat_j, lon_j)
                distances.append(dist)
                A[i, j] = dist
                A[j, i] = dist
                
    # Calcular pesos Gaussianos para la matriz de adyacencia
    if len(distances) > 0:
        sigma = np.std(distances) if np.std(distances) > 0 else np.mean(distances)
        if sigma == 0:
            sigma = 1000.0  # fallback a 1km
        
        for i in range(N):
            for j in range(N):
                if A[i, j] > 0:
                    A[i, j] = np.exp(- (A[i, j]**2) / (sigma**2))
    
    np.fill_diagonal(A, 1.0)
    
    print(f"Matriz de Adyacencia calculada con éxito. Densidad: {np.count_nonzero(A > 0) / (N*N) * 100:.2f}%")
    
    os.makedirs("data", exist_ok=True)
    
    metadata_path = "data/segment_metadata.csv"
    adj_path = "data/adjacency_matrix.npy"
    
    df_nodes.to_csv(metadata_path, index=False)
    np.save(adj_path, A)
    
    print(f"Metadata de segmentos guardada en: {metadata_path}")
    print(f"Matriz de adyacencia guardada en: {adj_path}")
    print("=== Proceso de Extraccion Completado ===")

if __name__ == "__main__":
    main()
