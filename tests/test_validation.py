import base64
import os
from io import BytesIO

import pytest
from unittest import mock

import generation_pb2
from server import GeneratorServicer
from grpc import StatusCode

class DummyContext:
    def __init__(self):
        self.code = None
        self.details_msg = None
    def set_code(self, code):
        self.code = code
    def set_details(self, details):
        self.details_msg = details

def test_empty_prompt():
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(request_id="id1", prompt="")
    resp = servicer.GenerateImage(req, ctx)
    assert ctx.code == StatusCode.INVALID_ARGUMENT
    assert ctx.details_msg == 'Prompt cannot be empty.'
    assert resp == generation_pb2.GenerateImageResponse()

def test_whitespace_prompt():
    servicer = GeneratorServicer()
    ctx = DummyContext()
    req = generation_pb2.GenerateImageRequest(request_id="id2", prompt="   \t  \n")
    resp = servicer.GenerateImage(req, ctx)
    assert ctx.code == StatusCode.INVALID_ARGUMENT
    assert ctx.details_msg == 'Prompt cannot be empty.'
    assert resp == generation_pb2.GenerateImageResponse()

def test_prompt_exact_512():
    servicer = GeneratorServicer()
    ctx = DummyContext()
    prompt = "a" * 512
    req = generation_pb2.GenerateImageRequest(request_id="id3", prompt=prompt)
    # Mock downstream calls to avoid real network/file ops
    with mock.patch('ollama_client.generate_image_from_prompt', return_value=(True, 'dGVzdA==', None)):
        with mock.patch('image_storage.save_image', return_value=(True, 'output/id3.png')):
            resp = servicer.GenerateImage(req, ctx)
    assert ctx.code is None  # success
    assert resp.request_id == "id3"
    assert resp.message == 'Image generated and saved successfully.'
    assert resp.image_path == 'output/id3.png'

def test_prompt_too_long():
    servicer = GeneratorServicer()
    ctx = DummyContext()
    prompt = "b" * 513
    req = generation_pb2.GenerateImageRequest(request_id="id4", prompt=prompt)
    resp = servicer.GenerateImage(req, ctx)
    assert ctx.code == StatusCode.INVALID_ARGUMENT
    assert ctx.details_msg == 'Prompt cannot exceed 512 characters.'
    assert resp == generation_pb2.GenerateImageResponse()
