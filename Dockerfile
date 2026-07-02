FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --no-input

# Port exposure
EXPOSE 8000

# Run migrations and start server with Daphne ASGI runner
CMD ["sh", "-c", "python manage.py migrate && daphne -b 0.0.0.0 -p 8000 rabbithouse_project.asgi:application"]
