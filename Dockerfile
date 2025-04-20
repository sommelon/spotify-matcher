# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y libpq-dev python3-dev build-essential

# Copy the current directory contents into the container at /app
COPY . /app

# Install Poetry
RUN pip install poetry

# Install Python dependencies
RUN poetry install --no-root --without dev

# Expose the port the app runs on
EXPOSE 5000

# Define environment variable
ENV NAME World

# Run the application
CMD ["poetry", "run", "flask", "run", "--host=0.0.0.0"]
