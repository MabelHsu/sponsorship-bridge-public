FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Initialize the SQLite database with mock brand data at build time
RUN python backend/db_tools.py

# Cleanup: Delete infra since the DB is already built
RUN rm -rf infra

EXPOSE 8080

CMD ["python", "backend/api_server.py"]
