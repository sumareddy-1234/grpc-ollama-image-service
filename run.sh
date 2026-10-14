#!/usr/bin/env bash

# Exit on any error
set -e

# Determine repository root (directory of this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Create virtual environment in .venv if it does not exist
if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python -m venv .venv
fi

# Activate the virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Generate protobuf bindings (re-run if source changed)
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. generation.proto

# Ensure output directory exists
mkdir -p output

# Start the gRPC server
python server.py
