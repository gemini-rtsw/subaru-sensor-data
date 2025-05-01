# Subaru Sensors System Architecture Design

## Overview
This document describes a simple system to expose Subaru sensor data as EPICS PVs and provide a basic web interface. The system consists of an EPICS IOC and a web server, both containerized for easy deployment.

## System Components

### 1. EPICS IOC (Input/Output Controller)
- **Technology**: 
  - EPICS 7.0.7+ with PVAccess protocol
  - Python 3.9+ with `p4p` library
- **PV Structure**:
  ```
  SUBARU:HUMIDITY:NE      (S1) - Humidity NE
  SUBARU:HUMIDITY:NW      (S2) - Humidity NW
  SUBARU:HUMIDITY:SE      (S3) - Humidity SE
  SUBARU:HUMIDITY:SW      (S4) - Humidity SW
  SUBARU:HUMIDITY:OBS     (S5) - OBS Floor Humidity
  SUBARU:HUMIDITY:CTRL    (S6) - Control Building Humidity
  SUBARU:HUMIDITY:OUTSIDE (S7) - Outside Humidity (mean)
  
  SUBARU:TEMP:NE          (S8) - Temperature NE
  SUBARU:TEMP:NW          (S9) - Temperature NW
  SUBARU:TEMP:SE         (S10) - Temperature SE
  SUBARU:TEMP:SW         (S11) - Temperature SW
  SUBARU:TEMP:OBS        (S12) - OBS Floor Temperature
  SUBARU:TEMP:CTRL       (S13) - Control Building Temperature
  SUBARU:TEMP:OUTSIDE    (S14) - Outside Temperature (mean)
  
  SUBARU:WIND:OPT        (S15) - Roof Opt Front Wind
  SUBARU:WIND:IR         (S16) - Roof IR Front Wind
  SUBARU:WIND:REAR       (S17) - Roof Rear Wind
  
  SUBARU:PRESSURE        (S18) - Atmospheric Pressure
  SUBARU:DEWPOINT        (S19) - Catwalk Dewpoint
  
  SUBARU:PARTICLES:ET:0.3-0.5  (S20) - Elevator Tower 0.3-0.5μm
  SUBARU:PARTICLES:ET:0.5-1.0  (S21) - Elevator Tower 0.5-1.0μm
  SUBARU:PARTICLES:ET:1.0-2.5  (S22) - Elevator Tower 1.0-2.5μm
  SUBARU:PARTICLES:ET:2.5-4.0  (S23) - Elevator Tower 2.5-4.0μm
  SUBARU:PARTICLES:ET:4.0-10.0 (S24) - Elevator Tower 4.0-10.0μm
  SUBARU:PARTICLES:ET:TOTAL    (S25) - Elevator Tower Total
  
  SUBARU:PARTICLES:OF:0.3-0.5  (S26) - Observation Floor 0.3-0.5μm
  SUBARU:PARTICLES:OF:0.5-1.0  (S27) - Observation Floor 0.5-1.0μm
  SUBARU:PARTICLES:OF:1.0-2.5  (S28) - Observation Floor 1.0-2.5μm
  SUBARU:PARTICLES:OF:2.5-4.0  (S29) - Observation Floor 2.5-4.0μm
  SUBARU:PARTICLES:OF:4.0-10.0 (S30) - Observation Floor 4.0-10.0μm
  SUBARU:PARTICLES:OF:TOTAL    (S31) - Observation Floor Total
  
  SUBARU:SO2:ET          (S40) - Elevator Tower SO2
  SUBARU:SO2:OF          (S41) - Observation Floor SO2
  SUBARU:SO2:NOAA        (S45) - NOAA SO2
  
  SUBARU:TIMESTAMP       (Epoch) - Unix Epoch Time
  ```
- **PV Types**:
  - All numeric values: `ai` (analog input)
  - Units and descriptions stored in EPICS fields
  - Scan rate: 1 second for all PVs
  - Alarm limits: 
    - Humidity: 0-100% RH
    - Temperature: -50 to 50°C
    - Wind: 0-100 m/s
    - Pressure: 0-2000 mbar
    - Particles: 0-1000 count/mL
    - SO2: 0-100 ppm

### 2. Web Server
- **Technology**: 
  - FastAPI 0.95.0+
  - Simple HTML/CSS/JavaScript frontend
- **Functionality**:
  - REST API to get current values
  - WebSocket for real-time updates
  - Basic web dashboard
  - Groups sensors by type (Humidity, Temperature, etc.)
  - Shows units and descriptions
  - Updates every second

### 3. Docker Deployment
- **Containers**:
  1. EPICS IOC Container
     - Base: CentOS 8
     - EPICS 7.0.7
     - Python 3.9
     - p4p library
     - Exposes port 5076 (PVA)

  2. Web Server Container
     - Base: Python 3.9
     - FastAPI
     - p4p client
     - Exposes port 8000 (HTTP)
     - Connects to IOC on port 5076

- **Docker Compose**:
  ```yaml
  version: '3'
  services:
    ioc:
      build: ./ioc
      ports:
        - "5076:5076"
      environment:
        - EPICS_CA_AUTO_ADDR_LIST=NO
        - EPICS_CA_ADDR_LIST=localhost

    web:
      build: ./web
      ports:
        - "8000:8000"
      depends_on:
        - ioc
      environment:
        - IOC_HOST=ioc
        - IOC_PORT=5076
  ```

## Implementation Notes
1. IOC will fetch data from the JSON URL every second
2. Web server will connect to IOC via PVAccess
3. Simple error handling and logging
4. No authentication required
5. No database needed
6. No complex UI - just basic tables and values

## Future Enhancements (Optional)
- Historical data storage
- Alarm configuration
- User authentication
- More advanced UI
- Mobile support 

# Example p4p PV creation
from p4p.server import Server
from p4p.server.thread import SharedPV
from p4p.nt import NTScalar

# Example creating single PV
humidity_ne_pv = SharedPV(
    nt=NTScalar('d'),
    initial=0.0
) 

GET /api/sensors - Get all sensor values
GET /api/sensors/humidity - Get all humidity sensors
GET /api/sensors/temperature - Get all temperature sensors
...
WebSocket /ws - Real-time updates 