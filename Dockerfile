FROM python:3.9

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    npm \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install fastapi uvicorn "docker>=6.1.0" requests

WORKDIR /app

COPY sandbox.py .
COPY . .

CMD ["uvicorn", "sandbox:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]