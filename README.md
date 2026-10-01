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

- **Humidity**: `subaru:humidity:*`
- **Temperature**: `subaru:temp:*`
- **Wind**: `subaru:wind:*`
- **Particles**: `subaru:particles:*`
- **SO2**: `subaru:so2:*`
- **Other**: `subaru:pressure`, `subaru:dewpoint`, `subaru:timestamp`

See [CA_CLIENT_SETUP.md](CA_CLIENT_SETUP.md) for EPICS client connection instructions.

## Web API

The web server provides the following API endpoints:

- `GET /api/sensors` - Get all sensor values
- `GET /api/sensors/groups` - Get sensors grouped by type
- `GET /api/sensors/{group_id}` - Get sensors for a specific group
- WebSocket at `/ws` - Real-time updates

## Development

### Deploying with systemd (production)

CI ([gemini-rtsw-ci](https://github.com/gemini-rtsw/gemini-rtsw-ci), a git
submodule) builds on every push to `main`:

- the app image `ghcr.io/gemini-rtsw/subaru-sensor-data:<version>-git<hash>`
  from the root `Dockerfile` (IOC and web server in one image), and
- the `subaru-sensor-data` noarch RPM, published to the shared rpm-repo.

The RPM ships only two systemd units, `subaru-sensors-ioc` and
`subaru-sensors-web`. Both run the image, pinned to the tag matching the RPM, and
their settings live in `/etc/sysconfig/subaru-sensors-{ioc,web}`. Those files
survive upgrades.

**`dnf install` does not pull the image.** Pre-pull it as a docker-group user
logged in to GHCR (a PAT (classic) with `read:packages`), then install and start:

```bash
docker pull ghcr.io/gemini-rtsw/subaru-sensor-data:<version>-git<hash>   # no sudo
sudo dnf install subaru-sensor-data-<version>-1.git<hash>.el9
sudo systemctl enable --now subaru-sensors-ioc subaru-sensors-web
journalctl -u subaru-sensors-ioc -f
curl -s localhost:8000/api/sensors | head -c 200
```

The tag to pull is the one in the unit: `grep IMAGE= /usr/lib/systemd/system/subaru-sensors-ioc.service`.

If you forget, the unit pulls it itself, **as the `software` user**. Root on
production hosts has no GHCR credentials; `software` is in the docker group and
logged in. It only pulls when the image is missing. On hosts without a
`software` account, such as dev machines, the unit fails with `Image ... is not
on this host. As a docker-group user run: docker pull ...` and retries every 5 s,
so it starts by itself once you have pulled.

**Upgrade:** pull the new tag, `dnf upgrade subaru-sensor-data-<nvr>`, then
`sudo systemctl restart subaru-sensors-ioc subaru-sensors-web`.
**Roll back:** `dnf downgrade subaru-sensor-data-<old nvr>` and restart. The old
image is normally still on the host; if not, pull it first.

**No GHCR access on the host at all:** on a machine that has it, run
`docker save <image> | gzip > image.tar.gz`, copy the file over, and run
`docker load < image.tar.gz`. Save by the full `ghcr.io/...` name so the loaded
tag matches the unit.

The docker-compose files below are for development. Do not run them alongside
the systemd units, because they use the same host ports.

### Building Docker Images

#### Compose Deployment (legacy)

**Linux Production (containers only, host networking)**
```bash
# Pull pre-built images from registry
docker-compose up -d
```

**Mac Production (containers only, bridge networking)**
```bash
# Pull pre-built images from registry  
docker-compose -f docker-compose.mac.yml up -d
```

#### Development (with local file editing)

**Linux Development (local files + host networking)**
```bash
# Build images locally
./build-images.sh

# Start with local file mounting for development
docker-compose -f docker-compose.dev.yml up -d
```

**Mac Development (local files + bridge networking)**
```bash
# Build images locally
./build-images.sh

# Start with local file mounting for development
docker-compose -f docker-compose.dev.mac.yml up -d
```

#### Configuration Files

- `docker-compose.yml` - **Linux production** (no local files)
- `docker-compose.mac.yml` - **Mac production** (no local files)  
- `docker-compose.dev.yml` - **Linux development** (with local files)
- `docker-compose.dev.mac.yml` - **Mac development** (with local files)

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
├── subaru-sensors.sh          # Service management script (start/stop/status/logs)
├── deploy.sh                  # Deployment script (registry pull or local build)
├── build-images.sh            # Local image build script
├── docker-compose.yml         # Linux production compose
├── docker-compose.mac.yml     # Mac production compose
├── docker-compose.dev.yml     # Linux development compose
├── docker-compose.dev.mac.yml # Mac development compose
├── CA_CLIENT_SETUP.md         # EPICS client connection guide
├── ioc/                       # EPICS IOC
│   ├── Dockerfile
│   ├── requirements.txt
│   └── ioc_server.py
└── web/                       # Web server
    ├── Dockerfile
    ├── requirements.txt
    ├── web_server.py
    └── templates/
        └── index.html         # Dashboard with EPICS connection info
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