FROM python:3.12-slim-bullseye
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN mkdir -p /app/data && chmod -R 777 /app/data
VOLUME /app/data
EXPOSE 5050
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "2", "--timeout", "60", "trustpilot_scraper:app"]