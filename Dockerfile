FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=spotify_matcher.flaskr:app

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /app

# Install Poetry
RUN pip install poetry


# Install dependencies
RUN poetry install --no-root --without dev

# Expose port
EXPOSE 5000

# Start the application
CMD ["poetry", "run", "gunicorn", "--bind", "0.0.0.0:5000", "$FLASK_APP"]
