from schemas.Chat import SystemMessage

from fastapi import WebSocket
from typing import Dict, Optional

import json
import logging
import asyncio
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Class to manage active WebSocket connections
class ConnectionManager:
    def __init__(self):
        # Dictionary to store active connections with unique IDs
        self.active_connections: Dict[str, WebSocket] = {}
        
    async def connect(self, websocket: WebSocket) -> str:
        """
        Accept a new WebSocket connection and assign it a unique ID.
        Returns the connection ID.
        """
        await websocket.accept()
        connection_id = str(uuid.uuid4())
        self.active_connections[connection_id] = websocket
        logger.info(f"New WebSocket connection established. ID: {connection_id}, Client: {websocket.client}")
        return connection_id
    
    def disconnect(self, connection_id: str):
        """
        Remove a WebSocket connection from active connections.
        """
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            del self.active_connections[connection_id]
            logger.info(f"WebSocket connection closed. ID: {connection_id}, Client: {websocket.client}")
    
    async def send_message(self, message: dict, connection_id: str) -> bool:
        """
        Send a message to a specific WebSocket connection.
        Returns True if sent successfully, False otherwise.
        """
        if connection_id not in self.active_connections:
            logger.warning(f"Attempted to send message to non-existent connection: {connection_id}")
            return False
            
        try:
            websocket = self.active_connections[connection_id]
            await websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Error sending message to connection {connection_id}: {e}")
            self.disconnect(connection_id)
            return False
    
    async def send_system_message(self, content: str, connection_id: str) -> bool:
        """
        Send a system message to a specific connection.
        """
        system_msg = SystemMessage(
            content=content,
            timestamp=asyncio.get_event_loop().time()
        )
        return await self.send_message(system_msg.dict(), connection_id)
    
    async def broadcast_message(self, message: dict):
        """
        Broadcast a message to all active connections.
        """
        disconnected_connections = []
        
        for connection_id, websocket in self.active_connections.items():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error broadcasting to connection {connection_id}: {e}")
                disconnected_connections.append(connection_id)
        
        # Clean up disconnected connections
        for connection_id in disconnected_connections:
            self.disconnect(connection_id)
    
    def get_active_connections_count(self) -> int:
        """
        Get the number of active connections.
        """
        return len(self.active_connections)

