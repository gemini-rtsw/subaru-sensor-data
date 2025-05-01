FROM python:3.9-slim

WORKDIR /app

# Install build dependencies for p4p
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose the web server port
EXPOSE 8000

# Run the web server
CMD ["uvicorn", "web_server:app", "--host", "0.0.0.0", "--port", "8000"] 