import os
import shutil
import threading
import time
import pytest
import grpc
from concurrent import futures

# Import generated protobuf
import generation_pb2
import generation_pb2_grpc

# Import server components
import server

def test_server_starts_on_configured_port(monkeypatch):
    # Use a random free port by setting env var
    monkeypatch.setattr(server.config.Config, 'grpc_port', 50052)
    # Start server in a thread
    def run():
        server.serve()
    t = threading.Thread(target=run, daemon=True)
    t.start()
    time.sleep(0.5)  # give server time to start
    # Check that the port is listening
    channel = grpc.insecure_channel('localhost:50052')
    try:
        grpc.channel_ready_future(channel).result(timeout=2)
        ready = True
    except Exception:
        ready = False
    assert ready, "gRPC server did not start on configured port"
    # Clean up
    channel.close()
    # Server will stop on process exit (daemon thread)

def test_output_directory_created(tmp_path, monkeypatch):
    # Ensure directory does not exist
    out_dir = tmp_path / "out"
    monkeypatch.setattr(server.config.Config, 'output_dir', str(out_dir))
    # Call save_image with dummy data
    from image_storage import save_image
    dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/5+BAQAE/wJ+fpm6AAAAAElFTkSuQmCC"
    success, path = save_image(dummy_b64, "test", str(out_dir))
    assert success
    # Directory should now exist
    assert out_dir.is_dir()
    # Image file should be written
    assert (out_dir / "test.png").exists()

def test_sanitize_unsafe_request_id():
    from image_storage import _sanitize_request_id
    unsafe = "../..\\evil/../..\\/../"
    safe = _sanitize_request_id(unsafe)
    # Should contain only alphanumerics, hyphen, underscore
    assert all(ch.isalnum() or ch in "_-" for ch in safe)
    # Should not be empty
    assert safe != ""

def test_atomic_write_failure(monkeypatch, tmp_path):
    from image_storage import save_image
    dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/5+BAQAE/wJ+fpm6AAAAAElFTkSuQmCC"
    # Force os.replace to raise OSError
    def bad_replace(src, dst):
        raise OSError("simulated failure")
    monkeypatch.setattr(os, "replace", bad_replace)
    success, err = save_image(dummy_b64, "id", str(tmp_path))
    assert not success
    assert "Failed to save image" in err

def test_concurrent_saves(tmp_path):
    from image_storage import save_image
    dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/5+BAQAE/wJ+fpm6AAAAAElFTkSuQmCC"
    results = []
    def worker(i):
        ok, path = save_image(dummy_b64, f"req{i}", str(tmp_path))
        results.append((ok, path))
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert all(r[0] for r in results)
    # Ensure 5 files exist
    files = list(tmp_path.glob("*.png"))
    assert len(files) == 5
