FROM python:3.12-slim

WORKDIR /app

COPY api-server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY api-server /app
COPY location-service /shared/location-service
COPY redis /shared/redis
COPY database /shared/database
COPY simulation /shared/simulation

ENV PYTHONPATH=/app:/shared/location-service:/shared/redis:/shared/database:/shared/simulation
ENV LOCATION_SERVICE_PATH=/shared/location-service

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
