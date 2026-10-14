"""
Server entry point for the gRPC image generation service.
"""
import os
import logging
from concurrent import futures
import grpc
from grpc import StatusCode

import generation_pb2, generation_pb2_grpc

import config
import ollama_client
import image_storage

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(name)s: %(message)s')

class GeneratorServicer(generation_pb2_grpc.GeneratorServicer):
    def GenerateImage(self, request, context):
        # Validation
        request_id = request.request_id or ""
        prompt = request.prompt or ""
        if not prompt.strip():
            context.set_code(StatusCode.INVALID_ARGUMENT)
            context.set_details('Prompt cannot be empty.')
            return generation_pb2.GenerateImageResponse()
        if len(prompt) > 512:
            context.set_code(StatusCode.INVALID_ARGUMENT)
            context.set_details('Prompt cannot exceed 512 characters.')
            return generation_pb2.GenerateImageResponse()

        # Call Ollama
        ok, image_b64, err_msg = ollama_client.generate_image_from_prompt(prompt)
        if not ok:
            # Map specific error messages to gRPC codes
            if err_msg == "Ollama service is not available.":
                context.set_code(StatusCode.UNAVAILABLE)
                context.set_details('Ollama service is not available.')
            elif err_msg == "Ollama service returned an error.":
                context.set_code(StatusCode.INTERNAL)
                context.set_details('Ollama service returned an error.')
            else:
                # Generic internal error for other cases
                context.set_code(StatusCode.INTERNAL)
                context.set_details(err_msg or 'Internal server error.')
            return generation_pb2.GenerateImageResponse()

        # Save image
        success, path_or_err = image_storage.save_image(image_b64, request_id, config.Config.output_dir)
        if not success:
            context.set_code(StatusCode.INTERNAL)
            context.set_details(path_or_err or 'Failed to save image.')
            return generation_pb2.GenerateImageResponse()

        # Build successful response
        return generation_pb2.GenerateImageResponse(
            request_id=request_id,
            message='Image generated and saved successfully.',
            image_path=path_or_err,
        )

def serve():
    os.makedirs(config.Config.output_dir, exist_ok=True)
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    generation_pb2_grpc.add_GeneratorServicer_to_server(GeneratorServicer(), server)
    listen_addr = f'0.0.0.0:{config.Config.grpc_port}'
    server.add_insecure_port(listen_addr)
    logger.info('Starting gRPC server on %s', listen_addr)
    server.start()
    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info('Shutting down server (KeyboardInterrupt)')
        server.stop(0)

if __name__ == '__main__':
    serve()
