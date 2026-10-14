"""
Unit tests for the AUTOMATIC1111 Stable Diffusion client and servicer integration.
"""
import base64
import pytest
from unittest import mock
from requests.exceptions import ConnectionError, Timeout, RequestException

from grpc import StatusCode
import generation_pb2
from server import GeneratorServicer
from sd_client import generate_image_from_prompt

# 1x1 valid PNG base64 fixture
VALID_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/5+BAQAE/wJ+fpm6AAAAAElFTkSuQmCC"

class DummyContext:
    def __init__(self):
        self.code = None
        self.details_msg = None

    def set_code(self, code):
        self.code = code

    def set_details(self, details):
        self.details_msg = details

# ----------------- Client Unit Tests -----------------

def test_sd_success(monkeypatch):
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {"images": [VALID_PNG_B64], "info": "{}"}
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)

    ok, img, err = generate_image_from_prompt("a photo of a smiling capybara")
    assert ok is True
    assert img == VALID_PNG_B64
    assert err is None

def test_sd_success_data_uri_prefix(monkeypatch):
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {"images": [f"data:image/png;base64,{VALID_PNG_B64}"]}
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)

    ok, img, err = generate_image_from_prompt("a capybara")
    assert ok is True
    assert img == VALID_PNG_B64
    assert err is None

def test_sd_http_error(monkeypatch):
    mock_response = mock.Mock()
    mock_response.ok = False
    mock_response.status_code = 500
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)

    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Image generation service returned an error."

def test_sd_connection_error(monkeypatch):
    def raise_conn(*args, **kwargs):
        raise ConnectionError("Connection refused")
    monkeypatch.setattr('requests.post', raise_conn)

    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Image generation service is not available."

def test_sd_timeout(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise Timeout("Request timed out")
    monkeypatch.setattr('requests.post', raise_timeout)

    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Image generation service is not available."

def test_sd_malformed_json(monkeypatch):
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.side_effect = ValueError("Invalid JSON")
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)

    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Malformed response from image generation service."

def test_sd_missing_images_field(monkeypatch):
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {"info": "{}"}
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)

    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Image generation response did not contain image data."

def test_sd_empty_images_array(monkeypatch):
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {"images": []}
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)

    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Image generation response did not contain image data."

def test_sd_invalid_image_type(monkeypatch):
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {"images": [12345]}
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)

    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Invalid image data returned by image generation service."

# ----------------- Servicer Integration Unit Tests -----------------

def test_sd_servicer_success(tmp_path):
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(
        request_id="sd-happy-001",
        prompt="a photo of a smiling capybara"
    )

    with mock.patch("server.config.Config.output_dir", str(tmp_path)):
        with mock.patch("sd_client.generate_image_from_prompt", return_value=(True, VALID_PNG_B64, None)):
            resp = servicer.GenerateImage(req, ctx)

    assert ctx.code is None
    assert resp.request_id == "sd-happy-001"
    assert resp.message == "Image generated and saved successfully."
    assert "sd-happy-001.png" in resp.image_path

    saved = tmp_path / "sd-happy-001.png"
    assert saved.exists()
    assert saved.stat().st_size > 0

def test_sd_servicer_unavailable():
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(request_id="sd-down", prompt="capybara")

    with mock.patch("sd_client.generate_image_from_prompt", return_value=(False, None, "Image generation service is not available.")):
        resp = servicer.GenerateImage(req, ctx)

    assert ctx.code == StatusCode.UNAVAILABLE
    assert ctx.details_msg == "Image generation service is not available."

def test_sd_servicer_http_error():
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(request_id="sd-err", prompt="capybara")

    with mock.patch("sd_client.generate_image_from_prompt", return_value=(False, None, "Image generation service returned an error.")):
        resp = servicer.GenerateImage(req, ctx)

    assert ctx.code == StatusCode.INTERNAL
    assert ctx.details_msg == "Image generation service returned an error."

def test_sd_servicer_invalid_base64(tmp_path):
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(request_id="sd-bad-b64", prompt="capybara")

    with mock.patch("server.config.Config.output_dir", str(tmp_path)):
        with mock.patch("sd_client.generate_image_from_prompt", return_value=(True, "not_valid_base64!@#$%", None)):
            resp = servicer.GenerateImage(req, ctx)

    assert ctx.code == StatusCode.INTERNAL
    assert "Invalid Base64" in ctx.details_msg

def test_sd_servicer_corrupt_image(tmp_path):
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(request_id="sd-corrupt", prompt="capybara")
    corrupt_b64 = base64.b64encode(b"this is plain text not an image").decode("utf-8")

    with mock.patch("server.config.Config.output_dir", str(tmp_path)):
        with mock.patch("sd_client.generate_image_from_prompt", return_value=(True, corrupt_b64, None)):
            resp = servicer.GenerateImage(req, ctx)

    assert ctx.code == StatusCode.INTERNAL
    assert "Invalid image data." in ctx.details_msg
