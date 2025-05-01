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
# Increase refresh rate to reduce load
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

# PV groups for organization - only include PVs that actually exist in the IOC
PV_GROUPS = {
    "humidity": {
        "name": "Humidity",
        "unit": "% RH",
        "pvs": [
            "SUBARU:HUMIDITY:OUTSIDE"
        ]
    },
    "temperature": {
        "name": "Temperature",
        "unit": "°C",
        "pvs": [
            "SUBARU:TEMP:OUTSIDE"
        ]
    },
    "other": {
        "name": "Other",
        "unit": "",
        "pvs": [
            "SUBARU:PRESSURE"
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
    ctx = Context('pva', conf={'EPICS_PVA_ADDR_LIST': IOC_HOST, 'EPICS_PVA_CONN_TMO': 2.0})
    
    # Get all PVs
    all_pvs = []
    for group in PV_GROUPS.values():
        all_pvs.extend(group["pvs"])
    
    # Add timestamp PV
    all_pvs.append("SUBARU:TIMESTAMP")
    
    logger.info(f"Monitoring {len(all_pvs)} PVs")
    
    while True:
        try:
            # Get all PV values
            for pv_name in all_pvs:
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
                    
                    timestamp = time.time()
                    
                    # Update the sensor value
                    sensor_values[pv_name] = {
                        "pv": pv_name,
                        "description": description,
                        "value": value,
                        "unit": unit,
                        "alarm": alarm,
                        "timestamp": timestamp
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
                            "timestamp": time.time()
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
    asyncio.create_task(update_sensor_values())

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
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
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
            "other": {
                "name": "Other",
                "unit": ""
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
                    if (groupId === 'humidity' && pv.includes('HUMIDITY')) return true;
                    if (groupId === 'temperature' && pv.includes('TEMP') && !pv.includes('TIMESTAMP')) return true;
                    if (groupId === 'other' && (pv.includes('PRESSURE') || pv.includes('DEWPOINT'))) return true;
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