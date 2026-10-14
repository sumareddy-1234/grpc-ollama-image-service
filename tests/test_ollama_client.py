import base64
import os
from io import BytesIO

import pytest
from unittest import mock

from ollama_client import generate_image_from_prompt
from requests.exceptions import ConnectionError, Timeout, RequestException

def test_ollama_success(monkeypatch):
    # Mock requests.post to return a valid JSON with images
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {"images": ["dGVzdA=="]}
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)
    ok, img, err = generate_image_from_prompt("test prompt")
    assert ok is True
    assert img == "dGVzdA=="
    assert err is None

def test_ollama_http_error(monkeypatch):
    mock_response = mock.Mock()
    mock_response.ok = False
    mock_response.status_code = 500
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)
    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Ollama service returned an error."

def test_ollama_connection_error(monkeypatch):
    def raise_conn(*args, **kwargs):
        raise ConnectionError("refused")
    monkeypatch.setattr('requests.post', raise_conn)
    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Ollama service is not available."

def test_ollama_timeout(monkeypatch):
    def raise_timeout(*args, **kwargs):
        raise Timeout("timed out")
    monkeypatch.setattr('requests.post', raise_timeout)
    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Ollama request timed out."

def test_ollama_malformed_json(monkeypatch):
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.side_effect = ValueError("bad json")
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)
    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "Malformed response from Ollama service."

def test_ollama_missing_images(monkeypatch):
    mock_response = mock.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {}
    monkeypatch.setattr('requests.post', lambda *args, **kwargs: mock_response)
    ok, img, err = generate_image_from_prompt("test")
    assert ok is False
    assert err == "No image data returned by Ollama."
