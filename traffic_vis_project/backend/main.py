from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import h5py
import os
import numpy as np
import pickle
import torch
from model import get_untrained_model

app = FastAPI(title="Traffic Vis PEMS-BAY API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

sensors_df = None
speed_data = None
timestamps = None
traffic_model = None
topology_edges = []

@app.on_event("startup")
def load_data():
    global sensors_df, speed_data, timestamps, traffic_model, topology_edges
    print("Loading datasets...")
    
    loc_file = os.path.join(DATA_DIR, 'graph_sensor_locations_bay.csv')
    if os.path.exists(loc_file):
        sensors_df = pd.read_csv(loc_file, names=['sensor_id', 'latitude', 'longitude'])
    
    h5_file = os.path.join(DATA_DIR, 'pems-bay.h5')
    if os.path.exists(h5_file):
        with h5py.File(h5_file, 'r') as f:
            speed_data = f['speed'][:]
            if 'timestamp' in f:
                ts = f['timestamp'][:]
                if isinstance(ts[0], bytes):
                    timestamps = [t.decode('utf-8') for t in ts]
                else:
                    timestamps = [str(t) for t in ts]

    num_nodes = speed_data.shape[1] if speed_data is not None else 325
    traffic_model = get_untrained_model(num_nodes=num_nodes)

    adj_file = os.path.join(DATA_DIR, 'adj_mx_bay.pkl')
    if os.path.exists(adj_file):
        with open(adj_file, 'rb') as f:
            sensor_ids, sensor_id_to_ind, adj_mx = pickle.load(f)
            for i in range(adj_mx.shape[0]):
                for j in range(adj_mx.shape[1]):
                    if i != j and adj_mx[i, j] > 0:
                        topology_edges.append({
                            "source": i,
                            "target": j,
                            "weight": float(adj_mx[i, j])
                        })

    print("Datasets loaded.")

@app.get("/api/sensors")
def get_sensors():
    if sensors_df is None:
        return {"error": "Sensors data not loaded."}
    
    if 'sensor_id' in sensors_df.columns:
        return sensors_df.to_dict(orient="records")
    return []

@app.get("/api/topology")
def get_topology():
    return topology_edges

@app.get("/api/traffic/snapshot")
def get_traffic_snapshot(time_index: int = 0):
    if speed_data is None:
        return {"error": "Speed data not loaded."}
    
    if time_index < 0 or time_index >= speed_data.shape[0]:
        return {"error": "Invalid time index."}
    
    # speed_data shape: (time, num_nodes, features)
    snapshot = speed_data[time_index, :, 0]
    
    return {
        "time_index": time_index,
        "timestamp": timestamps[time_index] if timestamps else None,
        "speeds": snapshot.tolist()
    }

@app.get("/api/traffic/history/{sensor_index}")
def get_sensor_history(sensor_index: int):
    if speed_data is None:
        return {"error": "Speed data not loaded."}
    
    if sensor_index < 0 or sensor_index >= speed_data.shape[1]:
        return {"error": "Invalid sensor index."}
        
    series = speed_data[:, sensor_index, 0]
    return {
        "sensor_index": sensor_index,
        "timestamps": timestamps if timestamps else list(range(len(series))),
        "history": series.tolist()
    }

@app.post("/api/predict/{sensor_index}")
def predict_traffic(sensor_index: int, time_index: int = 12):
    if speed_data is None or traffic_model is None:
        return {"error": "Data or Model not loaded."}
        
    history_len = 12
    start_idx = max(0, time_index - history_len)
    end_idx = time_index
    
    history_slice = speed_data[start_idx:end_idx, :, 0]
    
    if history_slice.shape[0] < history_len:
        pad_size = history_len - history_slice.shape[0]
        history_slice = np.pad(history_slice, ((pad_size, 0), (0, 0)), mode='edge')
        
    x = torch.tensor(history_slice, dtype=torch.float32)
    x = x.transpose(0, 1).unsqueeze(0)
    
    with torch.no_grad():
        pred = traffic_model(x) # (1, nodes, predict_len)
        
    pred = pred.squeeze(0) # (nodes, predict_len)
    
    sensor_pred = pred[sensor_index].numpy().tolist()
    
    future_timestamps = []
    if timestamps and time_index < len(timestamps):
        current_time = pd.to_datetime(timestamps[time_index - 1])
        future_times = pd.date_range(current_time + pd.Timedelta(minutes=5), periods=12, freq="5min")
        future_timestamps = [t.strftime('%Y-%m-%d %H:%M:%S') for t in future_times]
    
    sensor_history = history_slice[:, sensor_index].tolist()
    hist_timestamps = timestamps[start_idx:end_idx] if timestamps else []
    
    return {
        "sensor_index": sensor_index,
        "history": sensor_history,
        "history_timestamps": hist_timestamps,
        "prediction": sensor_pred,
        "prediction_timestamps": future_timestamps,
        "model": "Baseline PyTorch Linear"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
