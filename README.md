# gRPC Text-to-Image Generation Service with Ollama

A microservice built with Python and gRPC that bridges client requests with a local Ollama instance running multimodal / image generation models. The service receives prompt requests over a strictly-typed gRPC interface, validates input parameters, calls the local Ollama REST API (`/api/generate`), decodes the Base64 image payload, saves the resulting PNG image to the `output/` directory, and returns the relative path and request metadata.

## Prerequisites

- **Python**: Python 3.10+ (tested on Python 3.10, 3.11, 3.12, and 3.14)
- **Ollama**: Installed and running locally on port 11434
  - Linux/macOS: `curl -fsSL https://ollama.com/install.sh | sh`
  - Windows: Download and run the installer from [ollama.com](https://ollama.com/)
- **Ollama Model**: An Ollama-compatible model capable of multimodal or image output (default: `llava`):
  ```bash
  ollama pull llava
  ```
- **grpcurl** (Optional, for manual testing): Download from [github.com/fullstorydev/grpcurl](https://github.com/fullstorydev/grpcurl/releases)

> **Note on Model Behavior**: The default configured model is `llava`, in accordance with the assignment specification. In standard Ollama distributions, LLaVA is primarily a vision-language assistant; when queried with text-only prompts it produces textual output. If Ollama returns a response without an `images` array, the service safely returns an `INTERNAL` error (`Ollama response did not contain image data.`) and does not fabricate fake image files. To generate images, configure a model or endpoint that returns Base64 image data in the `images` array via the `OLLAMA_MODEL` and `OLLAMA_BASE_URL` environment variables.

## Setup and Installation

### 1. Clone or Open the Repository
```bash
cd grpc-ollama-image-service
```

### 2. Create and Activate Virtual Environment
**On Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**On Windows (PowerShell):**
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**On Windows (Command Prompt):**
```cmd
py -m venv .venv
.venv\Scripts\activate.bat
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Compile Protocol Buffers (if modifying generation.proto)
```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. generation.proto
```

## Running the Server

You can run the server directly or using the provided startup scripts.

### Automated Startup Script
The repository includes automated startup scripts:
- **Python (Cross-platform)**:
  ```bash
  python run.py
  ```
- **Bash (Linux / macOS / WSL)**:
  ```bash
  chmod +x run.sh
  ./run.sh
  ```
- **Windows Batch**:
  ```cmd
  start.bat
  ```

### Manual Execution
```bash
python server.py
```

The gRPC server will start and listen on port `50051` on all network interfaces (`0.0.0.0:50051`).

### Environment Configuration
The service supports the following environment variables:
- `OLLAMA_BASE_URL`: Base URL for Ollama API (default: `http://localhost:11434`)
- `OLLAMA_MODEL`: Model name to request (default: `llava`)
- `OLLAMA_TIMEOUT_SECONDS`: HTTP request timeout in seconds (default: `30`)
- `GRPC_PORT`: Port to bind gRPC server (default: `50051`)
- `OUTPUT_DIR`: Path to output directory (default: `output`)

## Testing with grpcurl

### 1. Inspect Service Definition (Reflection or Proto source)
```bash
grpcurl -plaintext -proto generation.proto localhost:50051 list
```

### 2. Successful Request (Happy Path)
```bash
grpcurl -plaintext -proto generation.proto -d '{"request_id": "happy-path-001", "prompt": "a photo of a smiling capybara"}' localhost:50051 generation.Generator.GenerateImage
```
Expected response:
```json
{
  "request_id": "happy-path-001",
  "message": "Image generated and saved successfully.",
  "image_path": "output/happy-path-001.png"
}
```

### 3. Failure Case: Empty Prompt
```bash
grpcurl -plaintext -proto generation.proto -d '{"request_id": "fail-empty", "prompt": ""}' localhost:50051 generation.Generator.GenerateImage
```
Expected gRPC Status: `INVALID_ARGUMENT` (Code 3)
Expected Details: `Prompt cannot be empty.`

### 4. Failure Case: Prompt Exceeds 512 Characters
```bash
grpcurl -plaintext -proto generation.proto -d '{"request_id": "fail-toolong", "prompt": "This prompt is repeated... (over 512 chars)"}' localhost:50051 generation.Generator.GenerateImage
```
Expected gRPC Status: `INVALID_ARGUMENT` (Code 3)
Expected Details: `Prompt cannot exceed 512 characters.`

### 5. Failure Case: Ollama Service Unavailable
When Ollama is stopped or unreachable at `http://localhost:11434`:
```bash
grpcurl -plaintext -proto generation.proto -d '{"request_id": "fail-down", "prompt": "a red car"}' localhost:50051 generation.Generator.GenerateImage
```
Expected gRPC Status: `UNAVAILABLE` (Code 14)
Expected Details: `Ollama service is not available.`

### 6. Failure Case: Downstream HTTP Error
When Ollama returns HTTP 500 / 4xx:
Expected gRPC Status: `INTERNAL` (Code 13)
Expected Details: `Ollama service returned an error.`

## Running Automated Tests

Run the test suite using pytest:
```bash
pytest -q
```
