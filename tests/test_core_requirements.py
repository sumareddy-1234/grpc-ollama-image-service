import os
import shutil
import base64
from pathlib import Path
from unittest import mock
import pytest
import grpc
from grpc import StatusCode

import generation_pb2
import generation_pb2_grpc
from server import GeneratorServicer
import config


class DummyContext:
    def __init__(self):
        self.code = None
        self.details_msg = None

    def set_code(self, code):
        self.code = code

    def set_details(self, details):
        self.details_msg = details


def test_core_req_1_proto_contract():
    """Verify generation.proto exists and matches the exact specification."""
    proto_path = Path("generation.proto")
    assert proto_path.exists(), "generation.proto must exist in the root directory"

    content = proto_path.read_text(encoding="utf-8")
    assert 'syntax = "proto3";' in content
    assert "package generation;" in content
    assert "service Generator" in content
    assert "rpc GenerateImage(GenerateImageRequest) returns (GenerateImageResponse);" in content
    assert "message GenerateImageRequest" in content
    assert "string request_id = 1;" in content
    assert "string prompt = 2;" in content
    assert "message GenerateImageResponse" in content
    assert "string image_path = 3;" in content


def test_core_req_3_happy_path_servicer(tmp_path):
    """Verify happy-path GenerateImage RPC saves PNG and returns exact response structure."""
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(
        request_id="happy-path-001",
        prompt="a photo of a smiling capybara"
    )

    # 1x1 transparent PNG in base64
    valid_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/5+BAQAE/wJ+fpm6AAAAAElFTkSuQmCC"

    with mock.patch("server.config.Config.output_dir", str(tmp_path)):
        with mock.patch("ollama_client.generate_image_from_prompt", return_value=(True, valid_png_b64, None)):
            resp = servicer.GenerateImage(req, ctx)

    assert ctx.code is None
    assert resp.request_id == "happy-path-001"
    assert resp.message == "Image generated and saved successfully."
    assert "happy-path-001.png" in resp.image_path
    
    saved_file = tmp_path / "happy-path-001.png"
    assert saved_file.exists(), "PNG file must be saved to output directory"
    assert saved_file.stat().st_size > 0, "PNG file must not be empty"


def test_core_req_4_empty_prompt():
    """Verify empty prompt returns INVALID_ARGUMENT with exact status details."""
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(request_id="invalid-empty-prompt", prompt="")
    resp = servicer.GenerateImage(req, ctx)

    assert ctx.code == StatusCode.INVALID_ARGUMENT
    assert ctx.details_msg == "Prompt cannot be empty."
    assert resp == generation_pb2.GenerateImageResponse()


def test_core_req_5_prompt_exceeding_512_chars():
    """Verify prompt > 512 characters returns INVALID_ARGUMENT with exact status details."""
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(request_id="invalid-long-prompt", prompt="a" * 513)
    resp = servicer.GenerateImage(req, ctx)

    assert ctx.code == StatusCode.INVALID_ARGUMENT
    assert ctx.details_msg == "Prompt cannot exceed 512 characters."
    assert resp == generation_pb2.GenerateImageResponse()


def test_core_req_6_ollama_unavailable():
    """Verify Ollama unavailable returns UNAVAILABLE with exact status details."""
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(request_id="ollama-down-test", prompt="any valid prompt")

    with mock.patch("ollama_client.generate_image_from_prompt", return_value=(False, None, "Ollama service is not available.")):
        resp = servicer.GenerateImage(req, ctx)

    assert ctx.code == StatusCode.UNAVAILABLE
    assert ctx.details_msg == "Ollama service is not available."
    assert resp == generation_pb2.GenerateImageResponse()


def test_core_req_7_ollama_http_error():
    """Verify Ollama non-200 returns INTERNAL with exact status details."""
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(request_id="ollama-err-test", prompt="any valid prompt")

    with mock.patch("ollama_client.generate_image_from_prompt", return_value=(False, None, "Ollama service returned an error.")):
        resp = servicer.GenerateImage(req, ctx)

    assert ctx.code == StatusCode.INTERNAL
    assert ctx.details_msg == "Ollama service returned an error."
    assert resp == generation_pb2.GenerateImageResponse()


def test_core_req_8_readme_headers():
    """Verify README.md exists and contains all required section headers."""
    readme_path = Path("README.md")
    assert readme_path.exists(), "README.md must exist in the root of the repository"

    content = readme_path.read_text(encoding="utf-8")
    required_headers = [
        "## Prerequisites",
        "## Setup and Installation",
        "## Running the Server",
        "## Testing with grpcurl",
    ]
    for header in required_headers:
        assert header in content, f"README.md must contain section header: {header}"


def test_core_req_9_startup_script_exists():
    """Verify at least one allowed startup script exists and is non-empty."""
    allowed = ["run.sh", "start.sh", "run.py", "start.py"]
    found = [s for s in allowed if Path(s).exists()]
    assert len(found) > 0, f"Repository must contain one of {allowed}"
    for script_name in found:
        assert Path(script_name).stat().st_size > 0


def test_core_req_10_output_dir_recreation(tmp_path):
    """Verify output directory is recreated automatically if missing."""
    out_dir = tmp_path / "deleted_output"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    assert not out_dir.exists()

    from image_storage import save_image
    valid_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/5+BAQAE/wJ+fpm6AAAAAElFTkSuQmCC"
    ok, path = save_image(valid_png_b64, "recreate-test", str(out_dir))

    assert ok is True
    assert out_dir.is_dir(), "Output directory must be created automatically"
    assert (out_dir / "recreate-test.png").exists()
