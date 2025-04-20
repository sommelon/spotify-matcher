# Dockerfile

FROM python:3.10-slim

# Set the working directory
WORKDIR /app

# Install Poetry (dependency manager)
RUN pip install poetry

# Copy Poetry configuration
COPY pyproject.toml poetry.lock /app/

# Install dependencies using Poetry (without dev dependencies for prod)
RUN poetry install --no-dev --no-root

# Copy the rest of the application files
COPY . /app/

# Expose the port that Flask will run on
EXPOSE 5000
