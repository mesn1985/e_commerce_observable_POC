FROM python:3.12-slim

WORKDIR /app

COPY shared/ /app/shared/

COPY services/order-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/order-service/app/ /app/app/

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]
