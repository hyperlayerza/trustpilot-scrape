# Use official Python runtime as base image
FROM python:3.12-slim-bullseye

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create volume for output
VOLUME /app/data

# Expose port
EXPOSE 5050

# Copy application code
COPY . .

# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5050", "app:app"]