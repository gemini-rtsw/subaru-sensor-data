FROM rockylinux:9

# Configure dnf for better network resilience
RUN echo "timeout=60" >> /etc/dnf/dnf.conf && \
    echo "retries=10" >> /etc/dnf/dnf.conf && \
    echo "minrate=1000" >> /etc/dnf/dnf.conf

# Enable CodeReady Builder (CRB) repository and install required packages
RUN dnf -y update && \
    dnf -y install dnf-plugins-core && \
    dnf config-manager --set-enabled crb && \
    dnf -y install --nobest --allowerasing python3 python3-devel gcc gcc-c++ make wget curl git readline-devel \
    perl-FindBin perl-File-Copy perl

# Install pip
RUN python3 -m ensurepip && \
    python3 -m pip install --upgrade pip

# Create app directory
WORKDIR /app

# Install EPICS from source
RUN mkdir -p /opt/epics && \
    cd /opt/epics && \
    (wget --timeout=30 --tries=3 --retry-connrefused --waitretry=5 \
         https://epics.anl.gov/download/base/base-7.0.7.tar.gz || \
     curl -L --connect-timeout 30 --retry 3 --retry-delay 5 \
         https://epics.anl.gov/download/base/base-7.0.7.tar.gz -o base-7.0.7.tar.gz || \
     wget --timeout=60 --tries=2 \
         https://github.com/epics-base/epics-base/archive/refs/tags/R7.0.7.tar.gz \
         -O base-7.0.7.tar.gz) && \
    tar -xzf base-7.0.7.tar.gz && \
    cd base-7.0.7 && \
    make -j4

# Set environment variables
ENV EPICS_BASE=/opt/epics/base-7.0.7
ENV EPICS_HOST_ARCH=linux-x86_64
ENV PATH="${EPICS_BASE}/bin/${EPICS_HOST_ARCH}:${PATH}"
ENV LD_LIBRARY_PATH="${EPICS_BASE}/lib/${EPICS_HOST_ARCH}:${LD_LIBRARY_PATH}"
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