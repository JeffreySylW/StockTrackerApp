FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY stock_tracker.py .
COPY stock_visualizer.py .

# Create volume for persistent data
VOLUME /app/data

# Set environment variables
ENV DATA_FILE=/app/data/stock_history.json

# Run the tracker by default
CMD ["python", "stock_tracker.py"]