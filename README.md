# Simple gRPC Text-to-Image Generation Service with Ollama

A production-grade Python microservice that receives text prompts over a strictly-typed gRPC API, validates request parameters, communicates with a local **Ollama** backend (`http://localhost:11434/api/generate` with model `llava` by default), decodes and validates the returned Base64 image payload, saves the image to `./output/<request_id>.png`, and returns a structured gRPC success response.

An optional **AUTOMATIC1111 Stable Diffusion WebUI** backend (`http://127.0.0.1:7860/sdapi/v1/txt2img`) is also included and selectable via the `IMAGE_BACKEND=sd` environment variable.

---

> [!NOTE]
> **Default Architecture & Model Behavior Notice**
> By default, the application runs the exact architecture specified by the original assignment:
> - **Default Backend**: Ollama (`http://localhost:11434/api/generate`) with model `llava`.
> - **Default Request Payload**: `{"model": "llava", "prompt": ..., "stream": false, "images": []}`.
> - **Model Reality**: Upstream Ollama uses the `images` parameter strictly as an *input* parameter for multimodal vision models. Standard Ollama models do not return an `images` field in output JSON.
> - **Assignment Compliance**: When the upstream Ollama response lacks an `images` array, the service faithfully executes the assignment's Section 2.3 reference pseudocode, returning gRPC `INTERNAL` with details `"Ollama response did not contain image data."`. The server never fabricates fake image files or fakes success.
> - **Optional Stable Diffusion Support**: For users wanting genuine text-to-image diffusion output, set `IMAGE_BACKEND=sd` to connect to a local AUTOMATIC1111 WebUI instance on port 7860.

---

## System Architecture

The service follows a modular, three-tier architecture separating client communication, service orchestration/validation, backend inference, and storage:

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
|            v 3. HTTP POST /api/generate (or /sdapi/v1/txt2img if sd)    |
|            |                                                            |
|            | 6. Return JSON response with image Base64                  |
|            v                                                            |
|  +----------------------------+   7. Save PNG   +---------------------+ |
|  | Image Decoding & Validation| --------------> | Output Directory    | |
|  | (Base64 decode + PIL check)|                 | (./output/<id>.png) | |
|  +----------------------------+                 +---------------------+ |
+-------------------------------------------------------------------------+
       |                                                    ^
       | HTTP POST {"model": "llava", "prompt": ...}        | JSON {"images": [...]}
       v                                                    |
+-------------------------------------------------------------------------+
|                    Downstream Backend (Ollama Default)                  |
|                         Ollama API (:11434)                             |
|           (Optional: AUTOMATIC1111 Stable Diffusion WebUI :7860)        |
+-------------------------------------------------------------------------+
```

### Step-by-Step Execution Flow
1. **GenerateImage RPC Call**: A client connects via gRPC and invokes `generation.Generator.GenerateImage` with `request_id` and `prompt`.
2. **Request Validation**: The server validates the request immediately (fails fast on empty strings, whitespace, or prompts exceeding 512 characters).
3. **HTTP POST to Downstream API**: If validation succeeds, the server constructs the required payload and sends an HTTP POST request to `http://localhost:11434/api/generate` (or to AUTOMATIC1111 if `IMAGE_BACKEND=sd`).
4. **Backend Processing**: The downstream model processes the request and returns JSON.
5. **Image Extraction**: The server inspects the JSON response for the `images` array. If missing/empty under Ollama, it returns gRPC `INTERNAL` (`Ollama response did not contain image data.`).
6. **Image Decoding & Integrity Check**: When image data is present, the first element of `images` is decoded via strict Base64 decoding and validated using Pillow (`PIL.Image.open`) to guarantee valid image bytes.
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

### Default Ollama Backend (`IMAGE_BACKEND=ollama`)

| Scenario | gRPC Status | Exact Status Details Message |
|---|---|---|
| Empty prompt (`""`) or whitespace (`"   "`) | `INVALID_ARGUMENT` (Code 3) | `Prompt cannot be empty.` |
| Prompt longer than 512 characters | `INVALID_ARGUMENT` (Code 3) | `Prompt cannot exceed 512 characters.` |
| Ollama service down / connection refused | `UNAVAILABLE` (Code 14) | `Ollama service is not available.` |
| Ollama returns non-200 HTTP status (4xx/5xx) | `INTERNAL` (Code 13) | `Ollama service returned an error.` |
| Missing `images` array / text-only output | `INTERNAL` (Code 13) | `Ollama response did not contain image data.` |
| Malformed JSON from Ollama | `INTERNAL` (Code 13) | `Malformed response from Ollama service.` |
| Request timed out | `UNAVAILABLE` (Code 14) | `Ollama service is not available.` |

### Optional Stable Diffusion Backend (`IMAGE_BACKEND=sd`)

| Scenario | gRPC Status | Exact Status Details Message |
|---|---|---|
| SD service down / connection refused | `UNAVAILABLE` (Code 14) | `Image generation service is not available.` |
| SD returns non-200 HTTP status | `INTERNAL` (Code 13) | `Image generation service returned an error.` |
| Missing `images` array | `INTERNAL` (Code 13) | `Image generation response did not contain image data.` |
| Malformed JSON from SD service | `INTERNAL` (Code 13) | `Malformed response from image generation service.` |

---

## Prerequisites

- **Python**: Python 3.10+ (tested on Python 3.10, 3.11, 3.12, and 3.14).
- **Ollama**: Installed and running locally on port 11434 (`http://localhost:11434`):
  - Windows: Download and run the installer from [ollama.com](https://ollama.com/).
  - Linux/macOS: `curl -fsSL https://ollama.com/install.sh | sh`.
- **Ollama Model**: Default model `llava`:
  ```bash
  ollama pull llava
  ```
- **grpcurl** (Optional, for manual CLI testing): Download from [github.com/fullstorydev/grpcurl](https://github.com/fullstorydev/grpcurl/releases).
- **Optional**: AUTOMATIC1111 Stable Diffusion WebUI running with `--api` on port 7860 (only needed if using `IMAGE_BACKEND=sd`).

---

## Setup and Installation

### 1. Clone or Open the Repository
```bash
cd grpc-ollama-image-service
```

### 2. Create and Activate Virtual Environment
**On Windows (PowerShell):**
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**On Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
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

### Automated Startup Scripts
The repository includes automated startup scripts:
- **Python (Cross-platform)**:
  ```bash
  python run.py
  ```
- **Windows Command Prompt**:
  ```cmd
  start.bat
  ```
- **Bash (Linux / macOS / WSL)**:
  ```bash
  ./run.sh
  ```

### Manual Execution
```powershell
python server.py
```
The server binds to `0.0.0.0:50051`.

### Environment Configuration

| Variable | Default | Purpose |
|---|---|---|
| `IMAGE_BACKEND` | `ollama` | Active backend: `ollama` (default) or `sd`. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama base URL. |
| `OLLAMA_MODEL` | `llava` | Ollama model name. |
| `OLLAMA_TIMEOUT_SECONDS` | `180` | Ollama timeout in seconds. |
| `SD_BASE_URL` | `http://127.0.0.1:7860` | AUTOMATIC1111 API base URL (when `IMAGE_BACKEND=sd`). |
| `SD_TIMEOUT_SECONDS` | `180` | Timeout in seconds for txt2img generation. |
| `SD_STEPS` | `15` | Inference steps for SD. |
| `SD_WIDTH` / `SD_HEIGHT` | `512` / `512` | Image dimensions in pixels for SD. |
| `GRPC_PORT` | `50051` | Port to bind gRPC server. |
| `OUTPUT_DIR` | `output` | Directory to save generated PNG images. |

---

## Testing with grpcurl

### 1. Inspect Service Definition
```bash
grpcurl -plaintext -proto generation.proto localhost:50051 list
```

### 2. Happy Path Request
```bash
grpcurl -plaintext -proto generation.proto -d '{"request_id": "happy-path-001", "prompt": "a photo of a smiling capybara"}' localhost:50051 generation.Generator.GenerateImage
```
Expected response (when image data is returned):
```json
{
  "request_id": "happy-path-001",
  "message": "Image generated and saved successfully.",
  "image_path": "output/happy-path-001.png"
}
```

### 3. Prompt Validation Errors
- **Empty prompt**:
  ```bash
  grpcurl -plaintext -proto generation.proto -d '{"request_id": "fail-empty", "prompt": ""}' localhost:50051 generation.Generator.GenerateImage
  ```
  Returns `INVALID_ARGUMENT`: `Prompt cannot be empty.`
- **Exceeding 512 characters**:
  Returns `INVALID_ARGUMENT`: `Prompt cannot exceed 512 characters.`

### 4. Downstream Error Scenarios (Ollama Default)
- **Ollama unavailable** (Ollama stopped):
  Returns `UNAVAILABLE`: `Ollama service is not available.`
- **Ollama HTTP error** (5xx/4xx):
  Returns `INTERNAL`: `Ollama service returned an error.`
- **Ollama text-only response** (no images array):
  Returns `INTERNAL`: `Ollama response did not contain image data.`

---

## How to Verify the Saved PNG

When an image is saved:
1. Verify the file exists:
   ```powershell
   Get-Item .\output\<request_id>.png
   ```
2. Verify image integrity with Python:
   ```powershell
   python -c "from PIL import Image; img = Image.open('output/happy-path-001.png'); print(img.format, img.size)"
   ```
3. Open in image viewer:
   ```powershell
   Start-Process .\output\happy-path-001.png
   ```

---

## Troubleshooting

1. **`INTERNAL: Ollama response did not contain image data.`**:
   This is expected with standard Ollama `llava` because LLaVA outputs text analysis rather than Base64 images. The service handles this upstream limitation safely according to assignment Section 2.3.
2. **`UNAVAILABLE: Ollama service is not available.`**:
   Ensure Ollama is running (`curl http://localhost:11434/api/tags`).
3. **Switching to Stable Diffusion**:
   To test with AUTOMATIC1111 txt2img, launch WebUI with `--api` on port 7860 and set `$env:IMAGE_BACKEND="sd"`.
4. **Port 50051 Conflict**:
   If port 50051 is in use, terminate the existing process or set `$env:GRPC_PORT="50052"`.

---

## Running Automated Tests

Run the full test suite using pytest:
```powershell
.\.venv\Scripts\python.exe -m pytest -v
```
All 43 tests verify proto contracts, prompt validation, atomic file storage, path traversal protection, Ollama client error mappings, SD client error mappings, and servicer integration.
