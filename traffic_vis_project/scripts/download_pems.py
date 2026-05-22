import os
import requests
import pandas as pd
import numpy as np
import h5py

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

def download_file(url, output_path):
    print(f"Downloading {url}...")
    try:
        response = requests.get(url)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"Saved to {output_path}")
    except Exception as e:
        print(f"Failed to download {url}: {e}")

def create_mock_pems_h5(filepath):
    print(f"Generating mock pems-bay.h5 for development at {filepath}...")
    # PEMS-BAY has 325 sensors. We mock 288 timesteps (1 day at 5-min intervals)
    num_sensors = 325
    num_timesteps = 288
    
    # Generate mock speeds between 30 and 70 mph
    mock_speed = np.random.uniform(low=30.0, high=70.0, size=(num_timesteps, num_sensors, 1))
    
    # Generate mock timestamps
    timestamps = pd.date_range("2017-01-01 00:00:00", periods=num_timesteps, freq="5min")
    timestamps_str = timestamps.strftime('%Y-%m-%d %H:%M:%S').values.astype('S')
    
    with h5py.File(filepath, 'w') as f:
        f.create_dataset('speed', data=mock_speed)
        # Often DCRNN stores time in a different format, but this is enough for mock
        f.create_dataset('timestamp', data=timestamps_str)
    print("Mock HDF5 generated.")

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Download small graph files from Graph-WaveNet repo
    urls = {
        'adj_mx_bay.pkl': 'https://raw.githubusercontent.com/nnzhan/Graph-WaveNet/master/data/sensor_graph/adj_mx_bay.pkl',
        'graph_sensor_locations_bay.csv': 'https://raw.githubusercontent.com/nnzhan/Graph-WaveNet/master/data/sensor_graph/graph_sensor_locations_bay.csv'
    }
    
    for filename, url in urls.items():
        out_path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(out_path):
            download_file(url, out_path)
        else:
            print(f"{filename} already exists.")
            
    h5_path = os.path.join(DATA_DIR, 'pems-bay.h5')
    if not os.path.exists(h5_path):
        create_mock_pems_h5(h5_path)
        print("\nNote: A mock pems-bay.h5 was created for UI development.")
        print("To train real models, replace it with the real pems-bay.h5 (e.g. from DCRNN repo).")
    else:
        print("pems-bay.h5 already exists.")

if __name__ == '__main__':
    main()
