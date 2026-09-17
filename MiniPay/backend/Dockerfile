FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so this layer is cached unless requirements.txt changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Configuration (DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, etc.) is
# supplied at "docker run" time via --env-file or -e, never baked into the
# image. See MiniPay/REPRODUCIBLE.md.
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
