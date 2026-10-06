FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN pip install --no-cache-dir -r requirements.lock.txt && playwright install --with-deps chromium
COPY jobbot ./jobbot
RUN useradd --create-home bot && mkdir /app/data && chown bot:bot /app/data
USER bot
ENV DATA_DIR=/app/data
EXPOSE 8000
CMD ["uvicorn", "jobbot.api:app", "--host", "0.0.0.0", "--port", "8000"]
