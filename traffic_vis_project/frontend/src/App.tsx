import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import Map from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer, LineLayer } from '@deck.gl/layers';
import { HeatmapLayer } from '@deck.gl/aggregation-layers';
import ReactECharts from 'echarts-for-react';
import { Activity, Play, Pause, ChevronRight, Map as MapIcon, GitMerge, Thermometer } from 'lucide-react';
import './App.css';

const API_BASE = 'http://localhost:8001/api';

// MapLibre basemap style
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

const INITIAL_VIEW_STATE = {
  longitude: -121.9,
  latitude: 37.3,
  zoom: 10,
  pitch: 45,
  bearing: 0
};

function App() {
  const [sensors, setSensors] = useState([]);
  const [timeIndex, setTimeIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [snapshot, setSnapshot] = useState(null);
  const [selectedSensor, setSelectedSensor] = useState(null);
  const [sensorHistory, setSensorHistory] = useState(null);
  const [predictionData, setPredictionData] = useState(null);
  const [isPredicting, setIsPredicting] = useState(false);
  
  const [viewMode, setViewMode] = useState('points'); // 'points', 'heatmap', 'topology'
  const [topology, setTopology] = useState([]);

  // Fetch sensors and topology on load
  useEffect(() => {
    axios.get(`${API_BASE}/sensors`).then(res => {
      setSensors(res.data);
    }).catch(err => console.error(err));
    
    axios.get(`${API_BASE}/topology`).then(res => {
      setTopology(res.data);
    }).catch(err => console.error(err));
  }, []);

  // Fetch snapshot when timeIndex changes
  useEffect(() => {
    axios.get(`${API_BASE}/traffic/snapshot?time_index=${timeIndex}`).then(res => {
      setSnapshot(res.data);
    }).catch(err => console.error(err));
  }, [timeIndex]);

  // Fetch history when a sensor is selected
  useEffect(() => {
    if (selectedSensor !== null) {
      setPredictionData(null); // Clear previous predictions
      axios.get(`${API_BASE}/traffic/history/${selectedSensor}`).then(res => {
        setSensorHistory(res.data);
      }).catch(err => console.error(err));
    }
  }, [selectedSensor]);

  // Handle Predict Button
  const handlePredict = async () => {
    if (selectedSensor === null) return;
    setIsPredicting(true);
    try {
      // Predict using history up to current timeIndex
      const res = await axios.post(`${API_BASE}/predict/${selectedSensor}?time_index=${timeIndex}`);
      setPredictionData(res.data);
    } catch (err) {
      console.error(err);
    } finally {
      setIsPredicting(false);
    }
  };

  // Playback logic
  useEffect(() => {
    let interval;
    if (isPlaying) {
      interval = setInterval(() => {
        setTimeIndex(prev => (prev + 1) % 288); // 288 = 1 day of 5-min intervals
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [isPlaying]);

  // Prepare deck.gl data
  const scatterplotData = useMemo(() => {
    if (!sensors.length || !snapshot) return [];
    
    return sensors.map((sensor, idx) => {
      const speed = snapshot.speeds[idx] || 0;
      // Color from Red (slow) to Green (fast)
      let color = [255, 0, 0];
      if (speed > 55) color = [0, 255, 0];
      else if (speed > 40) color = [255, 165, 0];
      else if (speed > 25) color = [255, 69, 0];
      
      return {
        position: [sensor.longitude, sensor.latitude],
        color,
        radius: 150, // meters
        sensorIndex: idx,
        speed
      };
    });
  }, [sensors, snapshot]);

  // Prepare LineLayer data (Topology)
  const lineData = useMemo(() => {
    if (viewMode !== 'topology' || !sensors.length || !topology.length) return [];
    return topology.map(edge => {
      const source = sensors[edge.source];
      const target = sensors[edge.target];
      if (!source || !target) return null;
      
      const speed = snapshot?.speeds[edge.source] || 0;
      let color = [255, 0, 0, 150];
      if (speed > 55) color = [0, 255, 0, 150];
      else if (speed > 40) color = [255, 165, 0, 150];
      
      return {
        sourcePosition: [source.longitude, source.latitude],
        targetPosition: [target.longitude, target.latitude],
        color
      };
    }).filter(Boolean);
  }, [topology, sensors, snapshot, viewMode]);

  const layers = [];
  
  if (viewMode === 'points') {
    layers.push(
      new ScatterplotLayer({
        id: 'sensors-layer',
        data: scatterplotData,
        pickable: true,
        opacity: 0.8,
        stroked: true,
        filled: true,
        radiusScale: 1,
        radiusMinPixels: 4,
        radiusMaxPixels: 10,
        lineWidthMinPixels: 1,
        getPosition: d => d.position,
        getFillColor: d => d.color,
        getLineColor: d => [255, 255, 255, 150],
        onClick: ({object}) => {
          if (object) setSelectedSensor(object.sensorIndex);
        }
      })
    );
  } else if (viewMode === 'heatmap') {
    layers.push(
      new HeatmapLayer({
        id: 'heatmap-layer',
        data: scatterplotData,
        getPosition: d => d.position,
        // Weight by congestion (slower = higher weight)
        getWeight: d => Math.max(0, 70 - d.speed),
        radiusPixels: 40,
        intensity: 2,
        threshold: 0.05
      })
    );
  } else if (viewMode === 'topology') {
    layers.push(
      new ScatterplotLayer({
        id: 'sensors-layer-faded',
        data: scatterplotData,
        pickable: true,
        opacity: 0.3,
        radiusMinPixels: 2,
        getPosition: d => d.position,
        getFillColor: [100, 100, 100],
        onClick: ({object}) => {
          if (object) setSelectedSensor(object.sensorIndex);
        }
      }),
      new LineLayer({
        id: 'topology-layer',
        data: lineData,
        getSourcePosition: d => d.sourcePosition,
        getTargetPosition: d => d.targetPosition,
        getColor: d => d.color,
        getWidth: 2,
      })
    );
  }

  // ECharts config
  const getChartOption = () => {
    if (!sensorHistory && !predictionData) return {};
    
    // Base data (Real History)
    let timestamps = sensorHistory ? sensorHistory.timestamps : [];
    let seriesData = sensorHistory ? sensorHistory.history : [];
    
    let predTimestamps = [];
    let predData = [];
    
    if (predictionData) {
      // Use prediction payload to show exact 12 steps history + 12 steps prediction
      timestamps = predictionData.history_timestamps;
      seriesData = predictionData.history;
      
      predTimestamps = predictionData.prediction_timestamps;
      predData = predictionData.prediction;
    }
    
    const allTimestamps = [...timestamps, ...predTimestamps];

    // Align prediction data to start after history
    const alignedPredData = new Array(timestamps.length).fill(null).concat(predData);
    const alignedHistData = seriesData.concat(new Array(predTimestamps.length).fill(null));

    return {
      tooltip: { trigger: 'axis' },
      grid: { left: '10%', right: '5%', bottom: '15%', top: '10%' },
      legend: {
        data: ['Real Speed', 'Prediction'],
        textStyle: { color: '#aaa' }
      },
      xAxis: {
        type: 'category',
        data: allTimestamps,
        axisLabel: { color: '#aaa', fontSize: 10 },
        axisLine: { lineStyle: { color: '#555' } }
      },
      yAxis: {
        type: 'value',
        name: 'Speed (mph)',
        nameTextStyle: { color: '#aaa' },
        axisLabel: { color: '#aaa' },
        splitLine: { lineStyle: { color: '#333' } }
      },
      series: [
        {
          name: 'Real Speed',
          type: 'line',
          data: alignedHistData,
          smooth: true,
          lineStyle: { width: 3, color: '#00f2fe' },
          symbol: 'none',
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [{ offset: 0, color: 'rgba(0,242,254,0.5)' }, { offset: 1, color: 'rgba(0,242,254,0)' }]
            }
          }
        },
        {
          name: 'Prediction',
          type: 'line',
          data: alignedPredData,
          smooth: true,
          lineStyle: { width: 3, color: '#ff4b2b', type: 'dashed' },
          symbol: 'circle',
          itemStyle: { color: '#ff4b2b' }
        }
      ]
    };
  };

  return (
    <div className="app-container">
      {/* Background Map */}
      <div className="map-container">
        <DeckGL
          initialViewState={INITIAL_VIEW_STATE}
          controller={true}
          layers={layers}
          getTooltip={({object}) => object && `Sensor ${object.sensorIndex}\nSpeed: ${object.speed.toFixed(1)} mph`}
        >
          <Map mapStyle={MAP_STYLE} />
        </DeckGL>
      </div>

      {/* Floating Header */}
      <header className="glass-panel header">
        <Activity className="icon" />
        <h1>b</h1>
        
        {/* View Mode Toggle */}
        <div className="view-toggle">
          <button 
            className={viewMode === 'points' ? 'active' : ''} 
            onClick={() => setViewMode('points')}
            title="Sensor Points"
          >
            <MapIcon size={18} />
          </button>
          <button 
            className={viewMode === 'heatmap' ? 'active' : ''} 
            onClick={() => setViewMode('heatmap')}
            title="Congestion Density"
          >
            <Thermometer size={18} />
          </button>
          <button 
            className={viewMode === 'topology' ? 'active' : ''} 
            onClick={() => setViewMode('topology')}
            title="Road Topology / Routes"
          >
            <GitMerge size={18} />
          </button>
        </div>
      </header>

      {/* Control Panel */}
      <div className="glass-panel controls">
        <div className="playback-controls">
          <button onClick={() => setIsPlaying(!isPlaying)} className="play-btn">
            {isPlaying ? <Pause size={20} /> : <Play size={20} />}
          </button>
          <div className="time-info">
            <span>Time Index: {timeIndex}</span>
            <span>{snapshot?.timestamp || '00:00:00'}</span>
          </div>
        </div>
        <input 
          type="range" 
          min="0" 
          max="287" 
          value={timeIndex} 
          onChange={(e) => setTimeIndex(parseInt(e.target.value))}
          className="slider"
        />
      </div>

      {/* Side Panel */}
      <div className={`glass-panel side-panel ${selectedSensor !== null ? 'open' : ''}`}>
        <div className="panel-header">
          <h2>Sensor {selectedSensor !== null ? selectedSensor : 'None'} Details</h2>
          <button onClick={() => setSelectedSensor(null)} className="close-btn"><ChevronRight /></button>
        </div>
        
        {selectedSensor !== null && (
          <div className="prediction-controls" style={{ marginBottom: '16px', display: 'flex', justifyContent: 'center' }}>
            <button 
              className="play-btn" 
              style={{ width: 'auto', padding: '8px 24px', borderRadius: '24px', fontWeight: 'bold' }}
              onClick={handlePredict}
              disabled={isPredicting}
            >
              {isPredicting ? 'Predicting...' : 'Predict Next Hour'}
            </button>
          </div>
        )}

        <div className="chart-container">
          {(sensorHistory || predictionData) ? (
            <ReactECharts option={getChartOption()} style={{ height: '300px', width: '100%' }} />
          ) : (
            <div className="placeholder">Select a sensor on the map</div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;
