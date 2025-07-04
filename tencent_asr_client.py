import asyncio
import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from typing import Callable, Dict
import uuid  # Import the uuid library

import websockets

logger = logging.getLogger(__name__)

class TencentASRClient:
    """
    Client for Tencent Cloud's real-time Automatic Speech Recognition (ASR) service via WebSocket.
    """
    BASE_URL = "wss://asr.cloud.tencent.com/asr/v2/"

    def __init__(self, app_id: str, secret_id: str, secret_key: str):
        if not all([app_id, secret_id, secret_key]):
            raise ValueError("Tencent ASR credentials (app_id, secret_id, secret_key) are required.")
        
        self.app_id = app_id
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.ws = None
        self.receive_task = None
        self.handlers: Dict[str, Callable[[dict], asyncio.Future]] = {}

    def _generate_signature(self) -> str:
        """
        Generates the signature required for authenticating with Tencent ASR WebSocket API.
        Reference: https://cloud.tencent.com/document/product/1093/48982#signature
        """
        # Define request parameters
        params = {
            "secretid": self.secret_id,
            "engine_model_type": "16k_zh",  # For Mandarin Chinese, 16kHz
            "timestamp": str(int(time.time())),
            "expired": str(int(time.time()) + 24 * 60 * 60),  # Expires in 24 hours
            "nonce": str(int(time.time()) % 100000),  # Random number
            # According to API docs and error msg, voice_format should be a number. '1' likely stands for pcm.
            "voice_format": "1",
            "voice_id": str(uuid.uuid4()),  # Add the required voice_id
        }

        # Construct the signature source string
        # 1. Sort parameters by key in alphabetical order
        sorted_params = sorted(params.items())
        # 2. Concatenate into a query string
        query_string = urllib.parse.urlencode(sorted_params)
        # 3. Construct the final string to be signed, following the specific ASR doc example
        host = "asr.cloud.tencent.com"
        path = f"/asr/v2/{self.app_id}"
        # The signature source string for Tencent ASR WebSocket seems to be a non-standard format
        source_string = f"{host}{path}?{query_string}"
        
        # Encrypt using HMAC-SHA1 and Base64 encode
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            source_string.encode('utf-8'),
            hashlib.sha1
        ).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')

        # URL-encode the signature and construct the final URL
        final_url = f"{self.BASE_URL}{self.app_id}?{query_string}&signature={urllib.parse.quote(signature_b64)}"
        
        logger.info(f"Generated Tencent ASR connection URL.")
        return final_url

    async def connect(self):
        """
        Connects to the Tencent ASR WebSocket server.
        """
        connection_url = self._generate_signature()
        self.ws = await websockets.connect(connection_url)
        logger.info("Successfully connected to Tencent ASR WebSocket server.")
        
        # Start the receiver coroutine
        self.receive_task = asyncio.create_task(self.receive_messages())

    async def receive_messages(self):
        """
        Listens for incoming messages and dispatches them to registered handlers.
        """
        try:
            async for message in self.ws:
                data = json.loads(message)
                # Tencent ASR does not have a 'type' field, we check 'code'
                if data.get("code") == 0:
                    # Successfully received data
                    handler = self.handlers.get("on_result", self.default_handler)
                    await handler(data)
                else:
                    # Error occurred
                    handler = self.handlers.get("on_error", self.default_handler)
                    await handler(data)
        except websockets.exceptions.ConnectionClosed as e:
            logger.error(f"Tencent ASR WebSocket connection closed: {e}")
            error_handler = self.handlers.get("on_close", self.default_handler)
            await error_handler({"error": str(e)})
        except Exception as e:
            logger.error(f"Error in receive_messages: {e}", exc_info=True)
            error_handler = self.handlers.get("on_error", self.default_handler)
            await error_handler({"error": str(e)})

    def register_handler(self, event_type: str, handler: Callable[[dict], asyncio.Future]):
        """
        Registers a handler for a specific event type (e.g., 'on_result', 'on_error').
        """
        self.handlers[event_type] = handler

    async def default_handler(self, data: dict):
        """
        Default handler for unhandled events.
        """
        logger.warning(f"Unhandled event data received from Tencent ASR: {data}")

    async def send_audio(self, audio_data: bytes):
        """
        Sends an audio chunk to the ASR service.
        """
        if self.ws and self.ws.open:
            await self.ws.send(audio_data)
        else:
            logger.error("WebSocket is not open. Cannot send audio.")

    async def send_end_frame(self):
        """
        Sends the end-of-stream signal to Tencent ASR.
        """
        if self.ws and self.ws.open:
            end_frame = json.dumps({"type": "end"})
            await self.ws.send(end_frame)
            logger.info("Sent end-of-stream frame to Tencent ASR.")
        else:
            logger.error("WebSocket is not open. Cannot send end frame.")

    async def close(self):
        """
        Closes the WebSocket connection.
        """
        if self.receive_task and not self.receive_task.done():
            self.receive_task.cancel()
            try:
                await self.receive_task
            except asyncio.CancelledError:
                pass
        
        if self.ws and self.ws.open:
            await self.ws.close()
            logger.info("Closed Tencent ASR WebSocket connection.") 