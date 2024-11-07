# Use Python 3.12 slim image as base
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY src/ src/
COPY pytest.ini .
COPY README.md .

# Environment variable defaults (can be overridden by Railway)
ENV DISCORD_TOKEN=""
ENV ANTHROPIC_API_KEY=""

# Command to run the bot
CMD ["python", "-m", "src.goals_bot"]

