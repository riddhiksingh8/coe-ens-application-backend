# Use a stable Python version
FROM python:3.10

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
    gcc \
    libffi-dev

# Upgrade pip before installing dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Pre-install bcrypt separately to avoid compilation errors
RUN pip install --no-cache-dir bcrypt

# Copy requirements file first to leverage caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . .

# Expose the FastAPI default port
EXPOSE 8000

# Run FastAPI with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
