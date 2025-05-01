#!/usr/bin/env python3
"""
Subaru Sensors IOC Server
Fetches data from the Subaru Sensors JSON endpoint and serves it as EPICS PVs.
"""

import time
import threading
import requests
from loguru import logger
from p4p import nt
from p4p.server import Server
from p4p.server.thread import SharedPV

# Configuration
SENSORS_URL = "https://www.naoj.org/Weather/data/SubaruSensors.json"
REFRESH_RATE = 1.0  # seconds

# Create PV mapping - Using the full list from web_server.py
pv_mapping = {
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
    # Adding timing/period sensors
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
    # Adding temperature sensors for SO2
    "S42": "subaru:temp:et:so2",
    "S43": "subaru:temp:of:so2",
    "S44": "subaru:timestamp:noaa:so2",
    "S45": "subaru:so2:noaa",
    "Epoch": "subaru:timestamp" # Assuming Epoch maps to the timestamp PV
}

class Handler(object):
    """Handler for SharedPV put operations"""
    
    def put(self, pv, op):
        """Handle put operation (update value)"""
        try:
            # Store the new value from the client
            pv.post(op.value())
            # Complete the operation
            op.done()
            logger.info(f"PV updated by client: {op.name()} = {op.value()}")
        except Exception as e:
            # Report error to client
            op.done(error=str(e))
            logger.error(f"Error handling put on {op.name()}: {e}")

class SubaruSensorsIOC:
    """Subaru Sensors IOC implementation"""
    
    def __init__(self):
        """Initialize the IOC with all PVs"""
        self.pvs = {}
        self.provider = {}
        self.running = True
        self.handler = Handler()
        
        # Create all PVs with initial values
        for sensor_id, pv_name in pv_mapping.items():
            # Create a scalar double PV, explicitly initialized to 0.0
            pv = SharedPV(nt=nt.NTScalar('d'),
                          initial=0.0, # Explicitly set initial value to 0.0
                          handler=self.handler)
            
            self.pvs[pv_name] = pv
            self.provider[pv_name] = pv
        
        # Start the data fetch thread
        self.thread = threading.Thread(target=self.update_loop, daemon=True)
    
    def start(self):
        """Start the IOC server"""
        logger.info("Starting Subaru Sensors IOC...")
        self.thread.start()
        
        # Create server with PV provider dictionary
        logger.info(f"Starting server with {len(self.provider)} PVs: {', '.join(self.provider.keys())}")
        server = Server(providers=[self.provider])
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down Subaru Sensors IOC...")
            self.running = False
            self.thread.join(timeout=2.0)
            server.stop()
    
    def update_loop(self):
        """Fetch sensor data periodically and update PVs"""
        logger.info(f"Data update loop started, refresh rate: {REFRESH_RATE}s")
        
        # Counter for periodic diagnostics
        update_count = 0
        
        while self.running:
            try:
                # Fetch sensor data
                logger.info(f"Fetching sensor data from {SENSORS_URL}")
                response = requests.get(SENSORS_URL, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Successfully fetched data with {len(data)} sensors")
                    
                    # Log first few sensor IDs to verify content
                    sample_sensors = list(data.keys())[:5]
                    logger.info(f"Sample sensor IDs in data: {sample_sensors}")
                    
                    # Update PVs with the data
                    self.update_pvs(data)
                    
                    # Periodically log the current state of all PVs (every 5 updates)
                    update_count += 1
                    if update_count % 5 == 0:
                        self.log_pv_values()
                else:
                    logger.error(f"Failed to fetch data: HTTP {response.status_code}")
            except Exception as e:
                logger.exception(f"Error fetching sensor data: {e}")
            
            # Wait for next update cycle
            time.sleep(REFRESH_RATE)
    
    def log_pv_values(self):
        """Log the current values of all PVs for diagnostic purposes"""
        logger.info("===== CURRENT PV VALUES =====")
        
        # Count how many PVs have non-zero values
        non_zero_count = 0
        
        # Sort PV names for consistent output
        pv_names = sorted(self.pvs.keys())
        
        for pv_name in pv_names:
            # For diagnostic purposes, we'll directly access the PV's current value
            # Note: In real EPICS usage, you'd use proper channel access methods
            try:
                # This is a simplification; actual implementation would depend on p4p internals
                # In p4p SharedPV, current value can be accessed through a special get call
                current_value = self.pvs[pv_name].current()
                
                # Count non-zero values
                if isinstance(current_value, (int, float)) and current_value != 0.0:
                    non_zero_count += 1
                
                logger.info(f"  PV: {pv_name} = {current_value}")
            except Exception as e:
                logger.warning(f"  Could not get value for PV {pv_name}: {e}")
        
        logger.info(f"Total PVs: {len(self.pvs)}, Non-zero values: {non_zero_count}")
        logger.info("==============================")
    
    def update_pvs(self, data):
        """Update PVs with new values from the data"""
        update_count = 0
        
        for sensor_id, pv_name in pv_mapping.items():
            if sensor_id in data:
                sensor_data = data[sensor_id]
                
                # Get the sensor value, defaulting to 0.0 for None values
                value = sensor_data.get('Value', 0.0)
                if value is None:
                    value = 0.0
                
                # Get description and units
                description = sensor_data.get('Description', f"Subaru Sensor {sensor_id}")
                units = sensor_data.get('Units', '')
                
                # Update PV value
                logger.info(f"Updating PV {pv_name} with value {value} {units}")
                # Post the update (use try-except for robustness if PV doesn't exist)
                try:
                    self.pvs[pv_name].post(value)
                    update_count += 1
                except KeyError:
                    logger.warning(f"PV {pv_name} not found in self.pvs dictionary. Skipping update.")
        
        logger.info(f"Updated {update_count} PVs out of {len(pv_mapping)} mapped sensors")

if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        "ioc_server.log",
        rotation="10 MB",
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {message}"
    )
    
    # Start the IOC
    logger.info("Initializing Subaru Sensors IOC")
    ioc = SubaruSensorsIOC()
    ioc.start() 