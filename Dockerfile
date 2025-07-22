FROM python:3.12-slim-bullseye
# Set working directory
WORKDIR /app

# Copy only requirements first to leverage caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code
COPY . .

# Expose the port Flask/Gunicorn will listen on
EXPOSE 5050

# Default command will be overridden by docker-compose
CMD ["gunicorn", "-k", "gevent", "-w", "2", "-b", "0.0.0.0:5050", "app:app"]