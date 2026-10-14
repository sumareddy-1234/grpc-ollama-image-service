import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables with defaults."""
    # Active backend: "ollama" (default) or "sd" (optional AUTOMATIC1111 txt2img)
    backend: str = os.getenv("IMAGE_BACKEND", "ollama")

    # AUTOMATIC1111 Stable Diffusion WebUI settings
    sd_base_url: str = os.getenv("SD_BASE_URL", "http://127.0.0.1:7860")
    sd_timeout: int = int(os.getenv("SD_TIMEOUT_SECONDS", "180"))
    sd_steps: int = int(os.getenv("SD_STEPS", "15"))
    sd_width: int = int(os.getenv("SD_WIDTH", "512"))
    sd_height: int = int(os.getenv("SD_HEIGHT", "512"))

    # Ollama settings (preserved for Ollama backend)
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llava")
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))

    # Service & Storage settings
    grpc_port: int = int(os.getenv("GRPC_PORT", "50051"))
    output_dir: str = os.getenv("OUTPUT_DIR", "output")
