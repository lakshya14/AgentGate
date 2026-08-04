# Use a slim Python 3.10 image to keep the container small
FROM python:3.10-slim

# Prevent Python from writing .pyc files and buffer stdout so logs stream instantly
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Security Best Practice: Create a non-root user named "appuser"
RUN useradd -m -r appuser

# Set the working directory inside the container
WORKDIR /app

# Copy dependency definition and install
# (We do this BEFORE copying the rest of the code to leverage Docker layer caching!)
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy the rest of our application code into the /app directory
COPY . .

# Give our non-root user ownership of the /app directory
RUN chown -R appuser:appuser /app

# Switch from root to our non-root user!
USER appuser

# Document that this container listens on port 8000
EXPOSE 8000

# Define the command to start the Uvicorn server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
