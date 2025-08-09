FROM python:3.10-slim

# Install only essential system dependencies
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/archives/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements-prod.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements-prod.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port (Cloud Run uses PORT environment variable)
EXPOSE 8080

# Run the application
CMD ["python", "main.py"]