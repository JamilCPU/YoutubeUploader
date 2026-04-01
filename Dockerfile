# Use Windows Server Core with Python 3.11
FROM python:3.11-windowsservercore

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create data directory for persistent storage
RUN mkdir C:\data

# Set environment variable for data directory
ENV DATA_DIR=C:\data
ENV WATCH_DIR=C:\watch

# Default entrypoint (can be overridden)
ENTRYPOINT ["python", "main.py"]
