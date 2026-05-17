#!/bin/bash
# Clean up the Docker Compose environment for the smoke tests

set -e

echo "Cleaning up Docker Compose environment..."
docker compose down -v

echo "✓ Cleanup complete"
