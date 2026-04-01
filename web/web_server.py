#!/usr/bin/env python3
"""
Subaru Sensors Web Server
Provides a web interface to the Subaru Sensors EPICS PVs.
"""

import os
import time
import json
import asyncio
from typing import Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from loguru import logger
from p4p.client.thread import Context

# Configuration
IOC_HOST = os.environ.get("IOC_HOST", "localhost")
IOC_PORT = os.environ.get("IOC_PORT", "5076")
REFRESH_RATE = 5.0  # seconds (increased from 1.0)

# Initialize FastAPI
app = FastAPI(title="Subaru Sensors Web Server",
              description="Web interface for Subaru Sensors EPICS PVs")

# Create templates directory
os.makedirs("templates", exist_ok=True)

# Set up templates
templates = Jinja2Templates(directory="templates")

# Create static directory
os.makedirs("static", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# PV groups for organization - expanded to include all the new sensors
PV_GROUPS = {
    "humidity": {
        "name": "Humidity",
        "unit": "% RH",
        "pvs": [
            "subaru:humidity:ne",
            "subaru:humidity:nw",
            "subaru:humidity:se",
            "subaru:humidity:sw",
            "subaru:humidity:obs",
            "subaru:humidity:ctrl",
            "subaru:humidity:outside"
        ]
    },
    "temperature": {
        "name": "Temperature",
        "unit": "°C",
        "pvs": [
            "subaru:temp:ne",
            "subaru:temp:nw",
            "subaru:temp:se",
            "subaru:temp:sw",
            "subaru:temp:obs",
            "subaru:temp:ctrl",
            "subaru:temp:outside",
            "subaru:dewpoint",
            "subaru:temp:et:so2",
            "subaru:temp:of:so2"
        ]
    },
    "wind": {
        "name": "Wind",
        "unit": "m/s",
        "pvs": [
            "subaru:wind:opt",
            "subaru:wind:ir",
            "subaru:wind:rear"
        ]
    },
    "pressure": {
        "name": "Pressure",
        "unit": "mbar",
        "pvs": [
            "subaru:pressure"
        ]
    },
    "particles": {
        "name": "Particle Concentration",
        "unit": "count/mL",
        "pvs": [
            "subaru:particles:et:0.3-0.5",
            "subaru:particles:et:0.5-1.0",
            "subaru:particles:et:1.0-2.5",
            "subaru:particles:et:2.5-4.0",
            "subaru:particles:et:4.0-10.0",
            "subaru:particles:et:total",
            "subaru:particles:of:0.3-0.5",
            "subaru:particles:of:0.5-1.0",
            "subaru:particles:of:1.0-2.5",
            "subaru:particles:of:2.5-4.0",
            "subaru:particles:of:4.0-10.0",
            "subaru:particles:of:total"
        ]
    },
    "so2": {
        "name": "SO2 Concentration",
        "unit": "ppm",
        "pvs": [
            "subaru:so2:et",
            "subaru:so2:of",
            "subaru:so2:noaa"
        ]
    },
    "timing": {
        "name": "Sample Timing",
        "unit": "seconds",
        "pvs": [
            "subaru:timestamp",
            "subaru:timing:et:particles",
            "subaru:timing:of:particles",
            "subaru:timing:et:so2",
            "subaru:timing:of:so2"
        ]
    },
    "timestamps": {
        "name": "Sample Timestamps",
        "unit": "seconds",
        "pvs": [
            "subaru:timestamp:et:particles",
            "subaru:timestamp:of:particles",
            "subaru:timestamp:et:so2",
            "subaru:timestamp:of:so2",
            "subaru:timestamp:noaa:so2"
        ]
    }
}

# Response models for API
class SensorValue(BaseModel):
    pv: str
    description: str
    value: float
    unit: str
    alarm: int
    timestamp: float

class SensorGroup(BaseModel):
    name: str
    unit: str
    sensors: List[SensorValue]

# Global state
sensor_values = {}
connections = set()

async def update_sensor_values():
    """Update sensor values from EPICS PVs"""
    # Create context for PVA access
    ctx = Context('pva', conf={'EPICS_PVA_ADDR_LIST': IOC_HOST, 'EPICS_PVA_CONN_TMO': '2.0'})

    # Get all PV names expected by the web interface from PV_GROUPS
    all_web_pvs = set()
    for group_info in PV_GROUPS.values():
        all_web_pvs.update(group_info['pvs'])

    logger.info(f"Web server monitoring {len(all_web_pvs)} PVs defined in PV_GROUPS")

    while True:
        try:
            # Update timestamp for all sensors
            current_time = time.time()

            # Attempt to update all PVs defined in PV_GROUPS from the IOC
            for pv_name in all_web_pvs:
                # Skip the timestamp PV here, we set it manually later
                if pv_name == "subaru:timestamp":
                    continue

                try:
                    # Get the value from PVA with a shorter timeout
                    pv_value = ctx.get(pv_name, timeout=2.0)
                    
                    # Handle different response formats based on what we get back
                    if hasattr(pv_value, 'get'):
                        # This is a structured value
                        value = float(pv_value.get('value', 0.0))
                        description = pv_value.get('display', {}).get('description', f"PV {pv_name}")
                        unit = pv_value.get('display', {}).get('units', '')
                        alarm = int(pv_value.get('alarm', {}).get('severity', 0))
                    else:
                        # This is a simple value
                        value = float(pv_value) if pv_value is not None else 0.0
                        description = f"PV {pv_name}"
                        unit = ""
                        alarm = 0
                    
                    # Don't overwrite existing description if we have it
                    if pv_name in sensor_values and sensor_values[pv_name]["description"] != f"PV {pv_name}":
                        description = sensor_values[pv_name]["description"]
                    
                    # Update the sensor value
                    sensor_values[pv_name] = {
                        "pv": pv_name,
                        "description": description,
                        "value": value,
                        "unit": unit,
                        "alarm": alarm,
                        "timestamp": current_time
                    }
                    
                except Exception as e:
                    logger.error(f"Error getting PV {pv_name}: {e}")
                    # Set a default fallback value to avoid errors
                    if pv_name not in sensor_values:
                        sensor_values[pv_name] = {
                            "pv": pv_name,
                            "description": f"PV {pv_name}",
                            "value": 0.0,
                            "unit": "",
                            "alarm": 3,  # Invalid
                            "timestamp": current_time
                        }
            
            # Update timestamp for all sensors to keep them fresh
            for pv_name in sensor_values:
                sensor_values[pv_name]["timestamp"] = current_time
            
            # Update the global timestamp
            sensor_values["subaru:timestamp"] = {
                "pv": "subaru:timestamp",
                "description": "Last update timestamp",
                "value": current_time,
                "unit": "seconds",
                "alarm": 0,
                "timestamp": current_time
            }
            
            # Broadcast updates to all WebSocket connections, but only if we have connections
            if connections:
                message = json.dumps({
                    "type": "update",
                    "data": sensor_values
                })
                
                for connection in list(connections):
                    try:
                        await connection.send_text(message)
                    except Exception as e:
                        logger.error(f"Error sending to WebSocket: {e}")
                        connections.discard(connection)
            
        except Exception as e:
            logger.exception(f"Error in update loop: {e}")
        
        # Wait for next update cycle
        await asyncio.sleep(REFRESH_RATE)

@app.on_event("startup")
async def startup_event():
    """Start the update task on startup"""
    # Initialize default values for all sensors from the provided data
    initialize_sensor_values()
    asyncio.create_task(update_sensor_values())

def initialize_sensor_values():
    """Initialize sensor values with predefined data"""
    # This function maps the provided JSON data to our PV structure
    sensors_data = {
        "S1": {"Description": "Catwalk Humidity NE", "Value": 100.0, "Units": "% RH"},
        "S2": {"Description": "Catwalk Humidity NW", "Value": 100.0, "Units": "% RH"},
        "S3": {"Description": "Catwalk Humidity SE", "Value": 100.0, "Units": "% RH"},
        "S4": {"Description": "Catwalk Humidity SW", "Value": 100.0, "Units": "% RH"},
        "S5": {"Description": "OBS Floor (TLSCP room) Humidity", "Value": 65.5, "Units": "% RH"},
        "S6": {"Description": "Control Building (Weather Tower) Humidity", "Value": 92.6, "Units": "% RH"},
        "S7": {"Description": "Outside Humidity (mean of all outside sensors)", "Value": 98.52, "Units": "% RH"},
        "S8": {"Description": "Catwalk Temperature NE", "Value": 3.3, "Units": "Deg C"},
        "S9": {"Description": "Catwalk Temperature NW", "Value": 1.8, "Units": "Deg C"},
        "S10": {"Description": "Catwalk Temperature SE", "Value": 3.2, "Units": "Deg C"},
        "S11": {"Description": "Catwalk Temperature SW", "Value": 1.8, "Units": "Deg C"},
        "S12": {"Description": "OBS floor (Front V) Temperature", "Value": 6.7, "Units": "Deg C"},
        "S13": {"Description": "Control Building (Weather Tower) Temperature", "Value": 5.0, "Units": "Deg C"},
        "S14": {"Description": "Outside Temperature (mean of all outside sensors)", "Value": 3.02, "Units": "Deg C"},
        "S15": {"Description": "Roof Opt Front Wind Velocity (mean)", "Value": 0.6, "Units": "m/s"},
        "S16": {"Description": "Roof IR Front Wind Velocity (mean)", "Value": 0.5, "Units": "m/s"},
        "S17": {"Description": "Roof Rear Wind Velocity (mean)", "Value": 0.2, "Units": "m/s"},
        "S18": {"Description": "Atmospheric Pressure", "Value": 620.5, "Units": "mbar"},
        "S19": {"Description": "Catwalk Dewpoint (mean of catwalk sensors)", "Value": 2.525, "Units": "Deg C"},
        "S20": {"Description": "Elevator Tower - Particulate concentration of size 0.3 to 0.5 micron", "Value": 0.0, "Units": "count/mL"},
        "S21": {"Description": "Elevator Tower - Particulate concentration of size 0.5 to 1.0 micron", "Value": 17.3553446664, "Units": "count/mL"},
        "S22": {"Description": "Elevator Tower - Particulate concentration of size 1.0 to 2.5 micron", "Value": 15.1479020649, "Units": "count/mL"},
        "S23": {"Description": "Elevator Tower - Particulate concentration of size 2.5 to 4.0 micron", "Value": 3.1485835181, "Units": "count/mL"},
        "S24": {"Description": "Elevator Tower - Particulate concentration of size 4.0 to 10.0 micron", "Value": 0.7853306664, "Units": "count/mL"},
        "S25": {"Description": "Elevator Tower - Particulate concentration of size 0.3 to 10.0 micron", "Value": 36.4371609158, "Units": "count/mL"},
        "S26": {"Description": "Observation floor - Particulate concentration of size 0.3 to 0.5 micron", "Value": 4.5512624847, "Units": "count/mL"},
        "S27": {"Description": "Observation floor - Particulate concentration of size 0.5 to 1.0 micron", "Value": 0.7730635272, "Units": "count/mL"},
        "S28": {"Description": "Observation floor - Particulate concentration of size 1.0 to 2.5 micron", "Value": 0.0366634528, "Units": "count/mL"},
        "S29": {"Description": "Observation floor - Particulate concentration of size 2.5 to 4.0 micron", "Value": 0.0062790182, "Units": "count/mL"},
        "S30": {"Description": "Observation floor - Particulate concentration of size 4.0 to 10.0 micron", "Value": 0.0022928185, "Units": "count/mL"},
        "S31": {"Description": "Observation floor - Particulate concentration of size 0.3 to 10.0 micron", "Value": 0.0022928185, "Units": "count/mL"},
        "S32": {"Description": "Elevator Tower - Particulate concentration sample/averaging period", "Value": 30.0, "Units": "seconds"},
        "S33": {"Description": "Observation floor - Particulate concentration sample/averaging period", "Value": 30.0, "Units": "seconds"},
        "S34": {"Description": "Elevator Tower - SO2 concentration sample/averaging period", "Value": 30.0, "Units": "seconds"},
        "S35": {"Description": "Observation floor - SO2 concentration sample/averaging period", "Value": 30.0, "Units": "seconds"},
        "S36": {"Description": "Elevator Tower - Particulate concentration sample timestamp", "Value": 1746057867.0, "Units": "seconds"},
        "S37": {"Description": "Observation floor - Particulate concentration sample timestamp", "Value": 1746057838.0, "Units": "seconds"},
        "S38": {"Description": "Elevator Tower - SO2 concentration sample timestamp", "Value": 1746057870.0, "Units": "seconds"},
        "S39": {"Description": "Observation floor - SO2 concentration sample timestamp", "Value": 1746057860.0, "Units": "seconds"},
        "S40": {"Description": "Elevator Tower - SO2 concentration (temperature corrected)", "Value": 0.0, "Units": "ppm"},
        "S41": {"Description": "Observation floor - SO2 concentration (temperature corrected)", "Value": 0.0, "Units": "ppm"},
        "S42": {"Description": "Elevator Tower - Air temperature (SO2 sensor)", "Value": 7.5723036631, "Units": "Deg C"},
        "S43": {"Description": "Observation floor - Air temperature (SO2 sensor)", "Value": 11.9443734941, "Units": "Deg C"},
        "S44": {"Description": "NOAA Sensor - SO2 concentration sample timestamp", "Value": 1746057866.0, "Units": "seconds"},
        "S45": {"Description": "NOAA Sensor - SO2 concentration", "Value": 0.003999, "Units": "ppm"},
        "Epoch": {"Description": "time since Unix epoch", "Value": 1746057962.2065122, "Units": "seconds"}
    }
    
    # Mapping of sensor codes to PV names
    sensor_to_pv = {
        "S1": "subaru:humidity:ne",
        "S2": "subaru:humidity:nw",
        "S3": "subaru:humidity:se",
        "S4": "subaru:humidity:sw",
        "S5": "subaru:humidity:obs",
        "S6": "subaru:humidity:ctrl",
        "S7": "subaru:humidity:outside",
        "S8": "subaru:temp:ne",
        "S9": "subaru:temp:nw",
        "S10": "subaru:temp:se",
        "S11": "subaru:temp:sw",
        "S12": "subaru:temp:obs",
        "S13": "subaru:temp:ctrl",
        "S14": "subaru:temp:outside",
        "S15": "subaru:wind:opt",
        "S16": "subaru:wind:ir",
        "S17": "subaru:wind:rear",
        "S18": "subaru:pressure",
        "S19": "subaru:dewpoint",
        "S20": "subaru:particles:et:0.3-0.5",
        "S21": "subaru:particles:et:0.5-1.0",
        "S22": "subaru:particles:et:1.0-2.5",
        "S23": "subaru:particles:et:2.5-4.0",
        "S24": "subaru:particles:et:4.0-10.0",
        "S25": "subaru:particles:et:total",
        "S26": "subaru:particles:of:0.3-0.5",
        "S27": "subaru:particles:of:0.5-1.0",
        "S28": "subaru:particles:of:1.0-2.5",
        "S29": "subaru:particles:of:2.5-4.0",
        "S30": "subaru:particles:of:4.0-10.0",
        "S31": "subaru:particles:of:total",
        "S32": "subaru:timing:et:particles",
        "S33": "subaru:timing:of:particles",
        "S34": "subaru:timing:et:so2",
        "S35": "subaru:timing:of:so2",
        "S36": "subaru:timestamp:et:particles",
        "S37": "subaru:timestamp:of:particles",
        "S38": "subaru:timestamp:et:so2",
        "S39": "subaru:timestamp:of:so2",
        "S40": "subaru:so2:et",
        "S41": "subaru:so2:of",
        "S42": "subaru:temp:et:so2",
        "S43": "subaru:temp:of:so2",
        "S44": "subaru:timestamp:noaa:so2",
        "S45": "subaru:so2:noaa",
        "Epoch": "subaru:timestamp"
    }
    
    # Create initial sensor values
    timestamp = time.time()
    for sensor_id, pv_name in sensor_to_pv.items():
        if sensor_id in sensors_data:
            sensor_data = sensors_data[sensor_id]
            unit = sensor_data["Units"]
            # Convert Deg C to °C for display consistency
            if unit == "Deg C":
                unit = "°C"
                
            # Set the initial value in our global sensor_values dict
            sensor_values[pv_name] = {
                "pv": pv_name,
                "description": sensor_data["Description"],
                "value": 0.0, # Set initial value to 0.0
                "unit": unit,
                "alarm": 0,  # Default to no alarm
                "timestamp": timestamp
            }
    
    # Make sure we have a timestamp
    if "subaru:timestamp" not in sensor_values:
        sensor_values["subaru:timestamp"] = {
            "pv": "subaru:timestamp",
            "description": "Last update timestamp",
            "value": 0.0, # Set initial timestamp value to 0.0
            "unit": "seconds",
            "alarm": 0,
            "timestamp": timestamp
        }
    
    logger.info(f"Initialized {len(sensor_values)} sensor values")

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML page"""
    with open("templates/index.html", "r") as f:
        return f.read()

@app.get("/api/sensors", response_model=Dict[str, SensorValue])
async def get_all_sensors():
    """Get all sensor values"""
    return sensor_values

@app.get("/api/sensors/groups", response_model=Dict[str, SensorGroup])
async def get_sensor_groups():
    """Get sensors grouped by type"""
    groups = {}
    
    for group_id, group_info in PV_GROUPS.items():
        # Get sensors for this group
        sensors = []
        for pv_name in group_info["pvs"]:
            if pv_name in sensor_values:
                sensors.append(SensorValue(**sensor_values[pv_name]))
        
        # Add group to result
        groups[group_id] = SensorGroup(
            name=group_info["name"],
            unit=group_info["unit"],
            sensors=sensors
        )
    
    return groups

@app.get("/api/sensors/{group_id}", response_model=SensorGroup)
async def get_sensor_group(group_id: str):
    """Get sensors for a specific group"""
    if group_id not in PV_GROUPS:
        return {"error": "Group not found"}
    
    group_info = PV_GROUPS[group_id]
    sensors = []
    
    for pv_name in group_info["pvs"]:
        if pv_name in sensor_values:
            sensors.append(SensorValue(**sensor_values[pv_name]))
    
    return SensorGroup(
        name=group_info["name"],
        unit=group_info["unit"],
        sensors=sensors
    )

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    connections.add(websocket)
    
    try:
        # Send initial data
        if sensor_values:
            await websocket.send_text(json.dumps({
                "type": "update",
                "data": sensor_values
            }))
        
        # Keep connection open
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connections.discard(websocket)

# Create index.html
@app.on_event("startup")
async def create_index_html():
    """Create the index.html file if it doesn't exist"""
    if not os.path.exists("templates/index.html"):
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Subaru Sensors Dashboard</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .header {
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            text-align: center;
            margin-bottom: 20px;
            border-radius: 5px;
        }
        .container {
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            justify-content: center;
        }
        .sensor-group {
            background-color: white;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            padding: 20px;
            min-width: 300px;
            max-width: 600px;
            flex: 1;
        }
        .sensor-group h2 {
            margin-top: 0;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
            color: #2c3e50;
        }
        .sensor-list {
            list-style: none;
            padding: 0;
        }
        .sensor-item {
            padding: 10px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
        }
        .sensor-item:last-child {
            border-bottom: none;
        }
        .sensor-name {
            font-weight: bold;
        }
        .sensor-value {
            font-family: monospace;
            min-width: 80px;
            text-align: right;
        }
        .alarm-0 { color: #2ecc71; } /* No alarm */
        .alarm-1 { color: #3498db; } /* Minor alarm */
        .alarm-2 { color: #f39c12; } /* Major alarm */
        .alarm-3 { color: #e74c3c; } /* Invalid */
        .status-bar {
            background-color: #2c3e50;
            color: white;
            padding: 10px 20px;
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            display: flex;
            justify-content: space-between;
        }
        .connection-status {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            margin-right: 10px;
        }
        .connected { background-color: #2ecc71; }
        .connecting { background-color: #f39c12; }
        .disconnected { background-color: #e74c3c; }
        @media (max-width: 768px) {
            .container {
                flex-direction: column;
            }
            .sensor-group {
                width: 100%;
                max-width: none;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Subaru Sensors Dashboard</h1>
    </div>
    
    <div class="container" id="sensor-groups">
        <!-- Sensor groups will be inserted here -->
        <div class="sensor-group">
            <h2>Loading data...</h2>
        </div>
    </div>
    
    <div class="status-bar">
        <div>
            <span class="connection-status disconnected" id="connection-status"></span>
            <span id="connection-text">Connecting...</span>
        </div>
        <div id="update-time">Last update: Never</div>
    </div>

    <script>
        // Global variables
        let sensorValues = {};
        let websocket = null;
        let reconnectTimer = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 5;
        
        // Group definitions (should match server-side)
        const sensorGroups = {
            "humidity": {
                "name": "Humidity",
                "unit": "% RH"
            },
            "temperature": {
                "name": "Temperature",
                "unit": "°C"
            },
            "wind": {
                "name": "Wind",
                "unit": "m/s"
            },
            "pressure": {
                "name": "Pressure",
                "unit": "mbar"
            },
            "particles": {
                "name": "Particle Concentration",
                "unit": "count/mL"
            },
            "so2": {
                "name": "SO2 Concentration",
                "unit": "ppm"
            },
            "timing": {
                "name": "Sample Timing",
                "unit": "seconds"
            }
        };
        
        // Initialize the dashboard
        function initDashboard() {
            const container = document.getElementById('sensor-groups');
            container.innerHTML = '';
            
            // Create a div for each sensor group
            for (const [groupId, group] of Object.entries(sensorGroups)) {
                container.innerHTML += `
                    <div class="sensor-group" id="group-${groupId}">
                        <h2>${group.name}</h2>
                        <ul class="sensor-list" id="sensors-${groupId}">
                            <li>Loading...</li>
                        </ul>
                    </div>
                `;
            }
            
            // Connect to websocket
            connectWebSocket();
        }
        
        // Connect to WebSocket with exponential backoff
        function connectWebSocket() {
            // Clear any pending reconnection
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
            
            // Update status
            updateConnectionStatus('connecting');
            
            // Create WebSocket with a timeout
            const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            websocket = new WebSocket(`${wsProtocol}//${window.location.host}/ws`);
            
            // Set timeout for connection
            const connectionTimeout = setTimeout(() => {
                if (websocket.readyState !== WebSocket.OPEN) {
                    websocket.close();
                    updateConnectionStatus('disconnected');
                    scheduleReconnect();
                }
            }, 5000);
            
            // Set up event handlers
            websocket.onopen = () => {
                clearTimeout(connectionTimeout);
                updateConnectionStatus('connected');
                reconnectAttempts = 0;
            };
            
            websocket.onmessage = (event) => {
                handleWebSocketMessage(event);
            };
            
            websocket.onclose = () => {
                clearTimeout(connectionTimeout);
                updateConnectionStatus('disconnected');
                scheduleReconnect();
            };
            
            websocket.onerror = (error) => {
                clearTimeout(connectionTimeout);
                console.error("WebSocket error:", error);
                websocket.close();
            };
        }
        
        // Handle WebSocket messages
        function handleWebSocketMessage(event) {
            try {
                const message = JSON.parse(event.data);
                
                if (message.type === 'update') {
                    sensorValues = message.data;
                    updateDashboard();
                    updateLastUpdateTime();
                }
            } catch (error) {
                console.error("Error handling WebSocket message:", error);
            }
        }
        
        // Update the dashboard with current values
        function updateDashboard() {
            for (const [groupId, group] of Object.entries(sensorGroups)) {
                const sensorList = document.getElementById(`sensors-${groupId}`);
                let html = '';
                
                // Map each PV to a group
                const groupPvs = Object.values(sensorValues).filter(sensor => {
                    const pv = sensor.pv;
                    if (groupId === 'humidity' && (pv.includes('humidity'))) return true;
                    if (groupId === 'temperature' && (pv.includes('temp') || pv.includes('dewpoint')) && !pv.includes('timestamp')) return true;
                    if (groupId === 'wind' && pv.includes('wind')) return true;
                    if (groupId === 'pressure' && pv.includes('pressure')) return true;
                    if (groupId === 'particles' && pv.includes('particles')) return true;
                    if (groupId === 'so2' && pv.includes('so2')) return true;
                    if (groupId === 'timing' && pv.includes('timestamp')) return true;
                    return false;
                });
                
                if (groupPvs.length === 0) {
                    html = '<li>No data available</li>';
                } else {
                    for (const sensor of groupPvs) {
                        html += `
                            <li class="sensor-item">
                                <span class="sensor-name">${sensor.description}</span>
                                <span class="sensor-value alarm-${sensor.alarm}">
                                    ${sensor.value.toFixed(2)} ${sensor.unit}
                                </span>
                            </li>
                        `;
                    }
                }
                
                sensorList.innerHTML = html;
            }
        }
        
        // Update connection status indicator
        function updateConnectionStatus(status) {
            const statusElement = document.getElementById('connection-status');
            const textElement = document.getElementById('connection-text');
            
            statusElement.className = `connection-status ${status}`;
            
            if (status === 'connected') {
                textElement.innerText = 'Connected';
            } else if (status === 'connecting') {
                textElement.innerText = 'Connecting...';
            } else if (status === 'disconnected') {
                textElement.innerText = 'Disconnected';
            }
        }
        
        // Update the last update time
        function updateLastUpdateTime() {
            const element = document.getElementById('update-time');
            const now = new Date();
            const timeString = now.toLocaleTimeString();
            element.innerText = `Last update: ${timeString}`;
        }
        
        // Schedule reconnection attempt with exponential backoff
        function scheduleReconnect() {
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
            }
            
            reconnectAttempts++;
            
            if (reconnectAttempts <= maxReconnectAttempts) {
                // Exponential backoff: 1s, 2s, 4s, 8s, 16s
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts - 1), 16000);
                
                reconnectTimer = setTimeout(() => {
                    connectWebSocket();
                }, delay);
            } else {
                // After max attempts, try reconnecting every 30 seconds
                reconnectTimer = setTimeout(() => {
                    reconnectAttempts = 0;
                    connectWebSocket();
                }, 30000);
            }
        }
        
        // Periodically ping the server to keep connection alive
        setInterval(() => {
            if (websocket && websocket.readyState === WebSocket.OPEN) {
                try {
                    websocket.send(JSON.stringify({ type: "ping" }));
                } catch (error) {
                    console.error("Error sending ping:", error);
                }
            }
        }, 30000);
        
        // Initialize on page load
        window.addEventListener('load', initDashboard);
    </script>
</body>
</html>
        """
        
        # Create the templates directory if it doesn't exist
        os.makedirs("templates", exist_ok=True)
        
        # Write the HTML file
        with open("templates/index.html", "w") as f:
            f.write(html)
        
        logger.info("Created index.html template")


if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        "web_server.log",
        rotation="10 MB",
        retention=5,
        compression="gz",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
    )
    
    # Start the web server
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 