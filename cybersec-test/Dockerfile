# FILE: Dockerfile (21 lines)
FROM python:3.12-slim

WORKDIR /app

# Install runtime deps
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir "textual>=0.70.0"

# Copy the swarm module
COPY swarm/ ./swarm/
COPY configs/ ./configs/
COPY samples/ ./samples/

# Install the package itself
RUN pip install --no-cache-dir -e .

# Default: show help
CMD ["python3", "-m", "swarm", "--help"]
