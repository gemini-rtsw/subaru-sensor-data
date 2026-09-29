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

**`dnf install` does not pull the image and does not start anything.** The
units pull the image as root when they start (`ExecStartPre=-docker pull`):

```bash
sudo dnf install subaru-sensor-data
sudo systemctl enable --now subaru-sensors-ioc subaru-sensors-web
journalctl -u subaru-sensors-ioc -f        # watch the first pull and start
curl -s localhost:8000/api/sensors | head -c 200
```

Upgrades behave the same way: `dnf upgrade` swaps in the new units, and the new
image is pulled on the next `sudo systemctl restart subaru-sensors-ioc subaru-sensors-web`.
Roll back with `dnf downgrade subaru-sensor-data` and restart.

#### Root must be able to pull from GHCR

gemini-rtsw images on GHCR are private, and the unit pulls as **root**, not as
you. Your own `docker login` does not count. If root has no credential, the
failure is quiet: the pull is best-effort, so `docker run` then reports
`Unable to find image ... denied` or `unauthorized`, and systemd restarts the
unit every 5 s. Check with `journalctl -u subaru-sensors-ioc`.

Do one of the following, once per host. You need a PAT (classic) with
`read:packages`.

1. **sudo allows docker:**
   ```bash
   echo "<PAT>" | sudo -H docker login ghcr.io -u <github-user> --password-stdin
   sudo docker pull ghcr.io/gemini-rtsw/subaru-sensor-data:latest    # proves root can pull
   ```
   `-H` is required. Without it, sudo may keep your `HOME`, so the login
   reports success but writes the credential to your own config, not root's.
2. **sudo does not allow docker, but you are in the `docker` group** (which is
   root-equivalent): log in as yourself, then copy the credential into root's
   home with a container:
   ```bash
   echo "<PAT>" | docker login ghcr.io -u <github-user> --password-stdin
   grep -q credsStore ~/.docker/config.json && echo "credential helper in use: copy will NOT work"
   docker run --rm -u 0 -v /root:/r -v "$HOME/.docker/config.json":/c:ro \
     ghcr.io/gemini-rtsw/subaru-sensor-data:latest \
     sh -c 'mkdir -p /r/.docker && cp /c /r/.docker/config.json'
   ```
   This overwrites any existing `/root/.docker/config.json`. It uses an image
   you have already pulled, so it works without Docker Hub access.
3. **Neither:** ask an admin to do (1), or make the package public
   (github.com/orgs/gemini-rtsw/packages/container/subaru-sensor-data/settings).
   With a public package, root needs no credential at all.

Stopgap only: `docker pull <the image in the unit>` as any docker-group user
puts the image in the shared daemon store, so the unit's pull becomes a no-op.
You would have to repeat it for every new version.

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