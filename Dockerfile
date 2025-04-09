# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
#ENV GOOGLE_APPLICATION_CREDENTIALS="/app/sowji-447920-108c16dc20ac.json"

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    curl \
    openssh-server && \
    rm -rf /var/lib/apt/lists/*  # Clean up apt cache

# Set up SSH configuration
RUN mkdir /var/run/sshd && \
    echo 'root:Docker!' | chpasswd && \
    chmod 600 /etc/ssh/sshd_config

# Copy SSH configuration file
COPY sshd_config.txt /etc/ssh/sshd_config

# Copy dependency files first for better Docker layer caching
COPY requirements.txt /app/requirements.txt

# Install dependencies
RUN pip install --default-timeout=100 --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the Django project files
COPY . .

# Copy start.sh and set it as executable
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose ports for Django and SSH
EXPOSE 8000 2222

# Start SSH and Django App
CMD ["/bin/bash", "/app/start.sh"]
