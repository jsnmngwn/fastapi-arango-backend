# Use official Python image as base
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential curl && rm -rf /var/lib/apt/lists/*

# Install Poetry using the official installation script
RUN curl -sSL https://install.python-poetry.org | python3 -

# Update PATH to include Poetry
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY pyproject.toml poetry.lock ./
COPY backend/ ./backend/
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi
COPY . .

# Expose port
EXPOSE 8000

# Start the FastAPI app
CMD ["poetry", "run", "python", "-m", "backend.main"]
