FROM python:3.12-slim

WORKDIR /app

# Copy shared utilities
COPY shared/ /app/shared/

# Install service dependencies
COPY services/product-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy service application code
COPY services/product-service/app/ /app/app/

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
