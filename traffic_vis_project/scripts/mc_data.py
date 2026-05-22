import os
import pandas as pd
import numpy as np
import pickle

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

def create_mock_locations(filepath):
    print(f"Generating mock sensor locations at {filepath}...")
    num_sensors = 325
    # SF Bay Area center roughly: 37.7749, -122.4194
    # Spread them around with some noise
    latitudes = np.random.normal(37.7749, 0.1, num_sensors)
    longitudes = np.random.normal(-122.4194, 0.1, num_sensors)
    
    df = pd.DataFrame({
        'sensor_id': np.arange(num_sensors),
        'latitude': latitudes,
        'longitude': longitudes
    })
    df.to_csv(filepath, index=False)
    print("Mock locations generated.")

def create_mock_adj_mx(filepath):
    print(f"Generating mock adjacency matrix at {filepath}...")
    num_sensors = 325
    # Random adjacency matrix
    adj_mx = np.random.rand(num_sensors, num_sensors)
    adj_mx = (adj_mx > 0.95).astype(float) # Sparse
    np.fill_diagonal(adj_mx, 1.0)
    
    with open(filepath, 'wb') as f:
        # PEMS adj_mx is usually stored as a tuple (sensor_ids, sensor_id_to_ind, adj_mx)
        sensor_ids = [str(i) for i in range(num_sensors)]
        sensor_id_to_ind = {str(i): i for i in range(num_sensors)}
        pickle.dump((sensor_ids, sensor_id_to_ind, adj_mx), f)
    print("Mock adjacency matrix generated.")

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    loc_path = os.path.join(DATA_DIR, 'graph_sensor_locations_bay.csv')
    if not os.path.exists(loc_path):
        create_mock_locations(loc_path)
        
    adj_path = os.path.join(DATA_DIR, 'adj_mx_bay.pkl')
    if not os.path.exists(adj_path):
        create_mock_adj_mx(adj_path)

if __name__ == '__main__':
    main()
