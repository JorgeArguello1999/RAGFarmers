from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from utils.chat import ConnectionManager

import json
import logging
import asyncio
import uuid


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Router for chat operations
router = APIRouter(prefix="/chat", tags=["Chat"])

# Global connection manager instance
manager = ConnectionManager()

async def process_prompt_async(prompt: str, connection_id: str, message_id: str):
    """
    Simulates a long-running asynchronous task (e.g., AI model inference).
    This function runs in the background and sends periodic updates.
    
    Args:
        prompt: The user's input prompt
        connection_id: The WebSocket connection ID
        message_id: Unique identifier for this message processing
    """
    try:
        # Send processing start notification
        await manager.send_system_message(
            f"Processing your request (ID: {message_id[:8]})...", 
            connection_id
        )
        
        logger.info(f"Starting AI model processing for prompt: '{prompt}' (Message ID: {message_id})")
        
        # Simulate AI model processing with periodic status updates
        total_steps = 5
        for step in range(1, total_steps + 1):
            await asyncio.sleep(1)  # Reduced from 5 seconds total to 1 second per step
            
            # Send progress update
            progress_msg = f"Processing step {step}/{total_steps}..."
            await manager.send_system_message(progress_msg, connection_id)
            logger.debug(f"Processing step {step}/{total_steps} for message {message_id}")
        
        # Simulate AI model response generation
        model_response = f"AI Model Response: I've processed your prompt '{prompt}' and here's my detailed response. This is a simulated AI response that would normally come from a language model or other AI system."
        
        # Send the final response
        response_message = {
            "type": "ai_response",
            "content": model_response,
            "message_id": message_id,
            "timestamp": asyncio.get_event_loop().time(),
            "status": "completed"
        }
        
        success = await manager.send_message(response_message, connection_id)
        
        if success:
            logger.info(f"Successfully completed processing for message {message_id}")
        else:
            logger.error(f"Failed to send final response for message {message_id}")
            
    except Exception as e:
        logger.error(f"Error in process_prompt_async for message {message_id}: {e}")
        
        # Send error message to client
        error_message = {
            "type": "error",
            "content": f"An error occurred while processing your request: {str(e)}",
            "message_id": message_id,
            "timestamp": asyncio.get_event_loop().time()
        }
        await manager.send_message(error_message, connection_id)

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat with an AI model.
    Supports structured message handling and background processing.
    """
    connection_id = await manager.connect(websocket)
    
    # Send welcome message
    welcome_msg = {
        "type": "system_message",
        "content": f"Welcome! Your connection ID is: {connection_id[:8]}. You can start chatting now.",
        "timestamp": asyncio.get_event_loop().time()
    }
    await manager.send_message(welcome_msg, connection_id)
    
    try:
        while True:
            # Wait for message from client
            raw_data = await websocket.receive_text()
            logger.info(f"Received data from connection {connection_id}: {raw_data}")
            
            try:
                # Try to parse as JSON for structured messages
                message_data = json.loads(raw_data)
                
                if isinstance(message_data, dict) and "content" in message_data:
                    prompt = message_data["content"]
                    message_type = message_data.get("type", "user_message")
                else:
                    # Fallback to treating the entire message as content
                    prompt = raw_data
                    message_type = "user_message"
                    
            except json.JSONDecodeError:
                # If it's not valid JSON, treat it as plain text
                prompt = raw_data
                message_type = "user_message"
            
            # Validate prompt is not empty
            if not prompt.strip():
                await manager.send_system_message("Please provide a non-empty message.", connection_id)
                continue
            
            # Generate unique message ID for tracking
            message_id = str(uuid.uuid4())
            
            # Start background processing task
            # The client doesn't need to wait here - processing happens asynchronously
            asyncio.create_task(
                process_prompt_async(prompt.strip(), connection_id, message_id)
            )
            
            logger.info(f"Started background processing for message {message_id} from connection {connection_id}")
            
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"Unexpected error in websocket_endpoint for connection {connection_id}: {e}")
    finally:
        manager.disconnect(connection_id)

@router.get("/stats")
async def get_connection_stats():
    """
    Get statistics about active WebSocket connections.
    """
    return {
        "active_connections": manager.get_active_connections_count(),
        "timestamp": asyncio.get_event_loop().time()
    }

@router.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {
        "status": "healthy",
        "service": "websocket_chat",
        "timestamp": asyncio.get_event_loop().time()
    }