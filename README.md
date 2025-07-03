# Subaru Sensors System

A system that exposes Subaru telescope sensor data as EPICS PVs and provides a web dashboard.

## Architecture

The system consists of two main components:

1. **EPICS IOC**: Fetches sensor data from JSON API and serves it as EPICS PVs
2. **Web Server**: Provides a web dashboard and API for accessing sensor data

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Git

### Running the System

1. Clone the repository:
   ```
   git clone https://github.com/your-repo/subaru-sensors.git
   cd subaru-sensors
   ```

2. Start the containers:
   ```
   docker-compose up -d
   ```

3. Access the dashboard:
   Open your browser and navigate to http://localhost:8000

### Stopping the System

```
docker-compose down
```

## EPICS PVs

The system exposes the following PV groups:

- **Humidity**: `SUBARU:HUMIDITY:*`
- **Temperature**: `SUBARU:TEMP:*`
- **Wind**: `SUBARU:WIND:*`
- **Particles**: `SUBARU:PARTICLES:*`
- **SO2**: `SUBARU:SO2:*`
- **Other**: `SUBARU:PRESSURE`, `SUBARU:DEWPOINT`, `SUBARU:TIMESTAMP`

## Web API

The web server provides the following API endpoints:

- `GET /api/sensors` - Get all sensor values
- `GET /api/sensors/groups` - Get sensors grouped by type
- `GET /api/sensors/{group_id}` - Get sensors for a specific group
- WebSocket at `/ws` - Real-time updates

## Development

### Building Docker Images

The system uses Docker images for deployment. Images are built automatically in CI/CD and pulled from the registry in production.

#### Production Deployment (Linux)

In production on Linux, `docker-compose` pulls pre-built images from the GitLab registry:

```bash
# Pull and start containers (Linux production)
docker-compose up -d
```

#### Mac Development

For Mac development, use the Mac-specific compose file due to Docker networking differences:

```bash
# Mac development
docker-compose -f docker-compose.mac.yml up -d
```

#### Local Development

For local development, use the build script to create images locally:

```bash
# Build both images locally
./build-images.sh
```

#### Manual Docker Build

You can also build the images manually if needed:

```bash
# Build IOC image
docker build -t subaru-sensors-ioc ./ioc

# Build web image
docker build -t subaru-sensors-web ./web
```

### Project Structure

```
├── docker-compose.yml         # Docker Compose configuration
├── ioc/                       # EPICS IOC
│   ├── Dockerfile             # IOC Docker configuration
│   ├── requirements.txt       # Python dependencies
│   └── ioc_server.py          # IOC server implementation
└── web/                       # Web server
    ├── Dockerfile             # Web Docker configuration
    ├── requirements.txt       # Python dependencies
    ├── web_server.py          # Web server implementation
    └── templates/             # HTML templates
        └── index.html         # Dashboard template
```

### Local Development

To develop locally without Docker:

1. Install requirements for IOC:
   ```
   cd ioc
   pip install -r requirements.txt
   ```

2. Install requirements for web server:
   ```
   cd web
   pip install -r requirements.txt
   ```

3. Run the IOC:
   ```
   cd ioc
   python ioc_server.py
   ```

4. Run the web server (in a different terminal):
   ```
   cd web
   python web_server.py
   ```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Data source: [Subaru Telescope](https://www.naoj.org/Weather/data/SubaruSensors.json)
- EPICS: [Experimental Physics and Industrial Control System](https://epics-controls.org/)
- p4p: [Python for EPICS PVAccess](https://github.com/mdavidsaver/p4p)
- FastAPI: [FastAPI Framework](https://fastapi.tiangolo.com/) 