"""
Startup script: installs dependencies, ensures bindings and output dir exist, and starts the gRPC server.
Satisfies Core Requirement 9 (run.py / start.sh / run.sh).
"""
import os
import sys
import subprocess
from pathlib import Path

def main():
    root_dir = Path(__file__).resolve().parent
    os.chdir(root_dir)

    req_file = root_dir / "requirements.txt"
    if req_file.exists():
        print(f"Installing dependencies from {req_file}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_file)])

    # Compile protobuf bindings if missing or generation.proto is newer
    proto_file = root_dir / "generation.proto"
    pb2_file = root_dir / "generation_pb2.py"
    pb2_grpc_file = root_dir / "generation_pb2_grpc.py"

    if proto_file.exists():
        need_compile = not pb2_file.exists() or not pb2_grpc_file.exists()
        if not need_compile:
            proto_mtime = proto_file.stat().st_mtime
            if proto_mtime > pb2_file.stat().st_mtime or proto_mtime > pb2_grpc_file.stat().st_mtime:
                need_compile = True
        
        if need_compile:
            print("Compiling Protocol Buffer bindings...")
            subprocess.check_call([
                sys.executable, "-m", "grpc_tools.protoc",
                "-I.", "--python_out=.", "--grpc_python_out=.", "generation.proto"
            ])

    # Ensure output directory exists (Requirement 10)
    output_dir = root_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Start the gRPC server (Requirement 2)
    print("Starting gRPC server...")
    import server
    server.serve()

if __name__ == "__main__":
    main()
