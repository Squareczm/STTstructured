import asyncio
import json
import os
import numpy as np
from fastapi import FastAPI, WebSocket, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
import uvicorn
import logging
from prompts import PROMPTS
from tencent_asr_client import TencentASRClient # Replaced OpenAI client
from starlette.websockets import WebSocketState
import wave
import datetime
import scipy.signal
from openai import OpenAI, AsyncOpenAI
from pydantic import BaseModel, Field
from typing import Generator, Optional
from llm_processor import get_llm_processor
from datetime import datetime, timedelta
import websockets.exceptions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic models for request and response schemas
class ReadabilityRequest(BaseModel):
    text: str = Field(..., description="The text to improve readability for.")
    prompt: Optional[str] = Field(None, description="Custom prompt for readability enhancement.")
    model: Optional[str] = Field(None, description="LLM model name, e.g. 'deepseek-chat' or 'deepseek-reasoner'.")

class ReadabilityResponse(BaseModel):
    enhanced_text: str = Field(..., description="The text with improved readability.")

class CorrectnessRequest(BaseModel):
    text: str = Field(..., description="The text to check for factual correctness.")
    prompt: Optional[str] = Field(None, description="Custom prompt for correctness checking.")
    model: Optional[str] = Field(None, description="LLM model name, e.g. 'deepseek-chat' or 'deepseek-reasoner'.")

class CorrectnessResponse(BaseModel):
    analysis: str = Field(..., description="The factual correctness analysis.")

class AskAIRequest(BaseModel):
    text: str = Field(..., description="The question to ask AI.")
    model: Optional[str] = Field(None, description="LLM model name, e.g. 'deepseek-chat' or 'deepseek-reasoner'.")

class AskAIResponse(BaseModel):
    answer: str = Field(..., description="AI's answer to the question.")

app = FastAPI()

# --- Environment Variable Configuration ---
TENCENT_APP_ID = os.getenv("TENCENT_APP_ID")
TENCENT_SECRET_ID = os.getenv("TENCENT_SECRET_ID")
TENCENT_SECRET_KEY = os.getenv("TENCENT_SECRET_KEY")

if not all([TENCENT_APP_ID, TENCENT_SECRET_ID, TENCENT_SECRET_KEY]):
    error_msg = "Tencent Cloud API credentials (TENCENT_APP_ID, TENCENT_SECRET_ID, TENCENT_SECRET_KEY) are not set in environment variables."
    logger.error(error_msg)
    raise EnvironmentError(error_msg)


# Initialize with DeepSeek as the default LLM
llm_processor = get_llm_processor("deepseek-chat")

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def get_realtime_page(request: Request):
    return FileResponse("static/realtime.html")

class AudioProcessor:
    def __init__(self, target_sample_rate=16000): # Changed to 16kHz for Tencent ASR
        self.target_sample_rate = target_sample_rate
        self.source_sample_rate = 48000  # Most common sample rate for microphones
        
    def process_audio_chunk(self, audio_data):
        # Convert binary audio data to Int16 array
        pcm_data = np.frombuffer(audio_data, dtype=np.int16)
        
        # Convert to float32 for better precision during resampling
        float_data = pcm_data.astype(np.float32) / 32768.0
        
        # Resample from 48kHz to 16kHz
        resampled_data = scipy.signal.resample_poly(
            float_data, 
            self.target_sample_rate, 
            self.source_sample_rate
        )
        
        # Convert back to int16 while preserving amplitude
        resampled_int16 = (resampled_data * 32768.0).clip(-32768, 32767).astype(np.int16)
        return resampled_int16.tobytes()

    def save_audio_buffer(self, audio_buffer, filename):
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)  # Mono audio
            wf.setsampwidth(2)  # 2 bytes per sample (16-bit)
            wf.setframerate(self.target_sample_rate)
            wf.writeframes(b''.join(audio_buffer))
        logger.info(f"Saved audio buffer to {filename}")

@app.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    logger.info("New WebSocket connection attempt")
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    
    await websocket.send_text(json.dumps({
        "type": "status",
        "status": "idle"
    }))
    
    client: TencentASRClient = None
    audio_processor = AudioProcessor()
    recording_stopped = asyncio.Event()
    asr_ready = asyncio.Event()
    pending_audio_chunks = [] # Buffer for audio chunks before ASR is ready
    
    async def initialize_asr():
        nonlocal client
        try:
            asr_ready.clear()
            
            client = TencentASRClient(
                app_id=TENCENT_APP_ID,
                secret_id=TENCENT_SECRET_ID,
                secret_key=TENCENT_SECRET_KEY
            )
            
            # Register handlers for Tencent ASR events BEFORE connecting
            client.register_handler("on_result", handle_asr_result)
            client.register_handler("on_error", handle_asr_error)
            client.register_handler("on_close", handle_asr_close)
            
            await client.connect()
            logger.info("Successfully connected to Tencent ASR client")
            
            # Wait a brief moment for the connection to stabilize
            await asyncio.sleep(0.1)
            
            # The connection is established, mark as ready
            asr_ready.set()

            # Send any buffered chunks immediately after connection
            if pending_audio_chunks:
                logger.info(f"Sending {len(pending_audio_chunks)} buffered audio chunks...")
                for chunk in pending_audio_chunks:
                    await client.send_audio(chunk)
                pending_audio_chunks.clear()
                logger.info("Buffered chunks sent.")

            await websocket.send_text(json.dumps({
                "type": "status",
                "status": "connected"
            }))
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Tencent ASR: {e}", exc_info=True)
            asr_ready.clear()
            await websocket.send_text(json.dumps({
                "type": "error",
                "content": "Failed to initialize Tencent ASR connection"
            }))
            return False

    async def handle_asr_result(data):
        if websocket.client_state == WebSocketState.CONNECTED:
            text = data.get("result", {}).get("voice_text_str", "")
            if text:
                await websocket.send_text(json.dumps({
                    "type": "text",
                    "content": text,
                    # Tencent ASR provides the full sentence each time, so it's always a "new response" in a way
                    "isNewResponse": True 
                }))
                logger.info(f"Handled ASR result: {text}")

            if data.get("final") == 1:
                logger.info("Final ASR result received.")
                recording_stopped.set()
                if client:
                    await client.close()


    async def handle_asr_error(data):
        error_msg = data.get("message", "Unknown ASR error")
        full_error = json.dumps(data, ensure_ascii=False)
        logger.error(f"Tencent ASR error: {full_error}") # Log the full error object
        await websocket.send_text(json.dumps({
            "type": "error",
            "content": f"ASR Error: {error_msg} (Details: {full_error})" # Send full details to frontend
        }))

    async def handle_asr_close(data):
        logger.warning(f"Tencent ASR connection closed: {data.get('error')}")
        asr_ready.clear()
        await websocket.send_text(json.dumps({
            "type": "status",
            "status": "idle"
        }))

    async def receive_messages():
        nonlocal client
        
        try:
            while True:
                if websocket.client_state == WebSocketState.DISCONNECTED:
                    logger.info("WebSocket client disconnected, stopping receiver.")
                    break
                    
                data = await websocket.receive()
                
                if "bytes" in data:
                    processed_audio = audio_processor.process_audio_chunk(data["bytes"])
                    if asr_ready.is_set() and client:
                        await client.send_audio(processed_audio)
                        logger.debug(f"Sent audio chunk to Tencent ASR, size: {len(processed_audio)} bytes")
                    else:
                        logger.debug("ASR not ready, buffering audio chunk.")
                        pending_audio_chunks.append(processed_audio)
                        
                elif "text" in data:
                    msg = json.loads(data["text"])
                    
                    if msg.get("type") == "start_recording":
                        await websocket.send_text(json.dumps({"type": "status", "status": "connecting"}))
                        if not await initialize_asr():
                            continue
                        recording_stopped.clear()
                    
                    elif msg.get("type") == "stop_recording":
                        logger.info("Received stop_recording message from client.")
                        if client and asr_ready.is_set():
                            await client.send_end_frame()
                        recording_stopped.set()

        except websockets.exceptions.ConnectionClosed:
            logger.info("Client WebSocket connection closed normally.")
        except Exception as e:
            logger.error(f"Error in receive_messages loop: {e}", exc_info=True)
        finally:
            if client:
                await client.close()
                logger.info("Tencent ASR client connection closed in finally block.")

    await receive_messages()
    logger.info("WebSocket connection handling finished.")

@app.post(
    "/api/v1/readability",
    response_model=ReadabilityResponse,
    summary="Enhance Text Readability",
    description="Improve the readability of the provided text using DeepSeek."
)
async def enhance_readability(request: ReadabilityRequest):
    try:
        async def text_generator():
            model_name = request.model or "deepseek-chat"
            processor = get_llm_processor(model_name)
            # Use custom prompt if provided, otherwise use default
            prompt = request.prompt or PROMPTS['readability-enhance']
            async for chunk in processor.process_text(request.text, prompt):
                yield chunk
        
        return StreamingResponse(text_generator(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Error in enhance_readability: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process text for readability.")

@app.post(
    "/api/v1/ask_ai",
    response_model=AskAIResponse,
    summary="Ask AI a Question",
    description="Ask AI to provide insights using DeepSeek model."
)
def ask_ai(request: AskAIRequest):
    try:
        model_name = request.model or "deepseek-chat"
        processor = get_llm_processor(model_name)
        answer = processor.process_text_sync(request.text, PROMPTS['paraphrase-gpt-realtime'])
        return AskAIResponse(answer=answer)
    except Exception as e:
        logger.error(f"Error in ask_ai: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get answer from AI.")

@app.post(
    "/api/v1/correctness",
    response_model=CorrectnessResponse,
    summary="一句话要点",
    description="生成约30-60字的一句话总结。"
)
async def check_correctness(request: CorrectnessRequest):
    try:
        async def text_generator():
            model_name = request.model or "deepseek-chat"
            processor = get_llm_processor(model_name)
            # Use custom prompt if provided, otherwise use default
            prompt = request.prompt or PROMPTS['correctness-check']
            async for chunk in processor.process_text(request.text, prompt):
                yield chunk

        return StreamingResponse(text_generator(), media_type="text/plain")
    except Exception as e:
        logger.error(f"Error in check_correctness: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to生成一句话要点。")

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=3006)
