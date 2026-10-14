# gRPC Text-to-Image Generation Service with Ollama

A production-grade Python microservice that receives text prompts over a strictly-typed gRPC API, validates request parameters, communicates with a local Ollama Large Language / multimodal Model (`/api/generate`), decodes and validates the returned Base64 image payload, saves the image to the `./output/` directory, and returns a structured gRPC success response.

---

## System Architecture

The service follows a modular, three-tier architecture separating client communication, service orchestration/validation, local AI inference, and storage:

```text
+-------------------------------------------------------------------------+
|                               Client Side                               |
|                     (e.g., grpcurl, Python client)                      |
+-------------------------------------------------------------------------+
       |                                                    ^
       | 1. GenerateImage RPC                               | 8. Return Success Response
       v                                                    |
+-------------------------------------------------------------------------+
|                      gRPC Server (My Application)                       |
|                        (server.py on port 50051)                        |
|                                                                         |
|  +---------------------+                                                |
|  | 2. Input Validation | (Reject empty, whitespace, or >512 char prompts)
|  +---------------------+                                                |
|            |                                                            |
|            v 3. HTTP POST /api/generate                                 |
|            |                                                            |
|            | 6. Return JSON response with image Base64                  |
|            v                                                            |
|  +----------------------------+   7. Save PNG   +---------------------+ |
|  | Image Decoding & Validation| --------------> | Output Directory    | |
|  | (Base64 decode + PIL check)|                 | (./output/<id>.png) | |
|  +----------------------------+                 +---------------------+ |
+-------------------------------------------------------------------------+
       |                                                    ^
       | HTTP POST {"model": "llava", ...}                  | JSON {"images": [...]}
       v                                                    |
+-------------------------------------------------------------------------+
|                           Local AI Environment                          |
|                       Ollama REST API (:11434)                          |
|                                                                         |
|            +-----------------------------------------------+            |
|            | 4. Process with Model (LLaVA multimodal model)|            |
|            | 5. Return image / inference data              |            |
|            +-----------------------------------------------+            |
+-------------------------------------------------------------------------+
```

### Step-by-Step Execution Flow
1. **GenerateImage RPC Call**: A client connects via gRPC and invokes `generation.Generator.GenerateImage` with `request_id` and `prompt`.
2. **Request Validation**: The server validates the request immediately (fails fast on empty strings, whitespace, or prompts exceeding 512 characters).
3. **HTTP POST to Ollama**: If validation succeeds, the server constructs a JSON payload (`{"model": "llava", "prompt": "...", "stream": false, "images": []}`) and sends an HTTP POST request to `http://localhost:11434/api/generate`.
4. **Model Inference**: Ollama loads the configured model (default `llava`) and performs local inference.
5. **Image Extraction**: The server inspects the JSON response for the `images` array.
6. **Image Decoding & Integrity Check**: The first element of `images` is decoded via strict Base64 decoding and validated using Pillow (`PIL.Image.open`) to guarantee valid image bytes.
7. **Atomic File Storage**: The server writes the image bytes atomically using temporary files (`.tmp` $\to$ final replace) into `./output/<request_id>.png`, protecting against path traversal and unsafe characters.
8. **Structured gRPC Response**: The server returns `GenerateImageResponse` echoing `request_id`, status message `"Image generated and saved successfully."`, and the relative path `output/<request_id>.png`.

---

## Exact Protocol Buffers Contract (`generation.proto`)

```protobuf
syntax = "proto3";

package generation;

service Generator {
  rpc GenerateImage(GenerateImageRequest) returns (GenerateImageResponse);
}

message GenerateImageRequest {
  string request_id = 1;
  string prompt = 2;
}

message GenerateImageResponse {
  string request_id = 1;
  string message = 2;
  string image_path = 3;
}
```

---

## Status Codes and Error Handling Specification

| Scenario | gRPC Status | Exact Status Details Message |
|---|---|---|
| Empty prompt (`""`) or whitespace (`"   "`) | `INVALID_ARGUMENT` (Code 3) | `Prompt cannot be empty.` |
| Prompt longer than 512 characters | `INVALID_ARGUMENT` (Code 3) | `Prompt cannot exceed 512 characters.` |
| Ollama service down / connection refused | `UNAVAILABLE` (Code 14) | `Ollama service is not available.` |
| Ollama returns non-200 HTTP status (4xx/5xx) | `INTERNAL` (Code 13) | `Ollama service returned an error.` |
| Missing `images` array or text-only model | `INTERNAL` (Code 13) | `No image data returned by Ollama.` |
| Malformed JSON from downstream | `INTERNAL` (Code 13) | `Malformed response from Ollama service.` |
| Request timed out | `INTERNAL` (Code 13) | `Ollama request timed out.` |

---

## Prerequisites

- **Python**: Python 3.10+ (tested on Python 3.10, 3.11, 3.12, and 3.14)
- **Ollama**: Installed and running locally on port 11434
  - Linux/macOS: `curl -fsSL https://ollama.com/install.sh | sh`
  - Windows: Download and run the installer from [ollama.com](https://ollama.com/)
- **Ollama Model**: The model configured in Ollama (default: `llava`):
  ```bash
  ollama pull llava
  ```
- **grpcurl** (Optional, for manual CLI testing): Download from [github.com/fullstorydev/grpcurl](https://github.com/fullstorydev/grpcurl/releases)

> **Model Capability Notice**: In standard Ollama distributions, LLaVA is a vision-language assistant; when queried with text-only prompts it produces textual output. If Ollama returns a response without an `images` array, the service safely returns an `INTERNAL` error (`No image data returned by Ollama.`) and never fabricates fake image files. To generate images, configure a model or endpoint that returns Base64 image data in the `images` array via the `OLLAMA_MODEL` and `OLLAMA_BASE_URL` environment variables.

---

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

---

## Running the Server

You can run the server directly or using the provided automated startup scripts.

### Automated Startup Script
The repository includes automated startup scripts satisfying Requirement 9:
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
- `OLLAMA_TIMEOUT_SECONDS`: HTTP request timeout in seconds (default: `60`)
- `GRPC_PORT`: Port to bind gRPC server (default: `50051`)
- `OUTPUT_DIR`: Path to output directory (default: `output`)

---

## Testing with grpcurl

### 1. Inspect Service Definition
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

---

## Running Automated Tests

Run the full test suite using pytest:
```bash
pytest -v
```

All 24 test cases verify the protobuf contract, validation rules, error codes, atomic writes, concurrency, output directory recreation, and Ollama integration.
