import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment variables with defaults."""
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llava")
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
    grpc_port: int = int(os.getenv("GRPC_PORT", "50051"))
    output_dir: str = os.getenv("OUTPUT_DIR", "output")
