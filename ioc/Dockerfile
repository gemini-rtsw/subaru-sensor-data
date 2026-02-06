FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl \
        wget \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Set environment variables (we'll use Python-only EPICS libraries)
ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV EPICS_PVA_ADDR_LIST=0.0.0.0
ENV EPICS_PVA_AUTO_ADDR_LIST=NO
ENV EPICS_PVA_BROADCAST_PORT=5076
ENV EPICS_PVA_SERVER_PORT=5075

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN python3 -m pip install -r requirements.txt

# Copy application code
COPY . .

# Expose the PVA port
EXPOSE 5076 5075

# Run the IOC
CMD ["python3", "ioc_server.py"] 