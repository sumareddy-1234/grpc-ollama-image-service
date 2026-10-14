@echo off

rem Determine script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

rem Create virtual environment if missing
if not exist .venv (
    echo Creating virtual environment... 
    python -m venv .venv
)

rem Activate virtual environment
call .venv\Scripts\activate.bat

rem Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

rem Generate protobuf bindings
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. generation.proto

rem Ensure output directory exists
if not exist output mkdir output

rem Start the gRPC server
python server.py
