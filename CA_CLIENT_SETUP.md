# Channel Access Client Setup

This IOC uses alternate EPICS ports (15064 for CA, 15075/15076 for PVA) to avoid conflicts with the native EPICS 7 IOC on the same host.

## For CA Clients to Connect to This IOC

Set these environment variables on your CA client systems:

```bash
export EPICS_CA_AUTO_ADDR_LIST=NO
export EPICS_CA_ADDR_LIST="<your-vm-ip>"
export EPICS_CA_SERVER_PORT=15064
```

Replace `<your-vm-ip>` with the IP address of your Rocky 8 VM (or use `localhost` if on the same host).

## Example Usage

```bash
# Set environment for this IOC
export EPICS_CA_AUTO_ADDR_LIST=NO
export EPICS_CA_ADDR_LIST="localhost"
export EPICS_CA_SERVER_PORT=15064

# Test connection
caget subaru:pressure
camonitor subaru:temp:outside
```

## For PVAccess Clients

```bash
export EPICS_PVA_AUTO_ADDR_LIST=NO
export EPICS_PVA_ADDR_LIST="<your-vm-ip>"
export EPICS_PVA_BROADCAST_PORT=15076
export EPICS_PVA_SERVER_PORT=15075

# Test connection
pvget subaru:humidity:ne
```

## For Native EPICS 7 IOC Clients

Keep the standard environment (or unset the above variables):

```bash
unset EPICS_CA_SERVER_PORT
export EPICS_CA_AUTO_ADDR_LIST=YES
# or set EPICS_CA_ADDR_LIST to your network's broadcast address
```

## Port Summary

| Service | Standard Ports | This IOC Ports | Purpose |
|---------|---------------|----------------|---------|
| CA Search/Server | 5064 UDP+TCP | 15064 UDP+TCP | Client searches, server connections |
| PVA Server | 5075 TCP | 15075 TCP | PVA data |
| PVA Broadcast | 5076 UDP | 15076 UDP | PVA search |

The native EPICS 7 IOC continues to use the standard ports (5064/5065), while this dockerized IOC uses the alternate ports (15064/15075/15076).
