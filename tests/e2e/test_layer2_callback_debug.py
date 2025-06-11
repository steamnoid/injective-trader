# Debug test for Layer 2 callback functionality
"""
Debug test to understand what's happening in our InjectiveStreamClient callbacks
"""

import pytest
import asyncio
import logging
import time
from datetime import datetime, timezone
from pyinjective import AsyncClient
from pyinjective.core.network import Network

from injective_bot.connection import (
    ConnectionState, MessageType, WebSocketMessage, MessageHandler
)
from injective_bot.connection.injective_client import InjectiveStreamClient
from injective_bot.config import WebSocketConfig

# Configure detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class CallbackDebugCollector(MessageHandler):
    """Message collector with callback debugging"""
    
    def __init__(self):
        self.messages = []
        self.callback_calls = 0
        
    def get_supported_message_types(self):
        return [MessageType.ORDERBOOK, MessageType.TRADES, MessageType.MARKET_DATA]
    
    async def handle_message(self, message: WebSocketMessage) -> None:
        """Handle message with debug logging"""
        logger.info(f"HANDLER CALLED: {message.message_type.value} for {message.market_id}")
        self.messages.append(message)


class TestLayer2CallbackDebug:
    """Debug tests for callback functionality"""
    
    @pytest.mark.asyncio
    async def test_debug_callback_flow(self):
        """Debug the entire callback flow"""
        logger.info("Starting callback flow debug test...")
        
        config = WebSocketConfig(
            max_reconnect_attempts=1,
            connection_timeout=30.0,
            ping_interval=30.0,
            max_message_rate=1000
        )
        
        client = InjectiveStreamClient(config=config, network="mainnet")
        collector = CallbackDebugCollector()
        client.register_handler(collector)
        
        # Add debug hooks to see what's happening
        original_determine_message_type = client._determine_message_type
        original_extract_market_id = client._extract_market_id
        
        def debug_determine_message_type(data):
            logger.info(f"DETERMINING MESSAGE TYPE for data: {type(data)}")
            if isinstance(data, dict):
                logger.info(f"Data keys: {list(data.keys())[:5]}...")  # First 5 keys
            result = original_determine_message_type(data)
            logger.info(f"Determined message type: {result}")
            return result
        
        def debug_extract_market_id(data):
            logger.info(f"EXTRACTING MARKET ID from data: {type(data)}")
            result = original_extract_market_id(data)
            logger.info(f"Extracted market ID: {result}")
            return result
        
        client._determine_message_type = debug_determine_message_type
        client._extract_market_id = debug_extract_market_id
        
        try:
            # Connect
            logger.info("Connecting to mainnet...")
            result = await asyncio.wait_for(client.connect(), timeout=30.0)
            
            if not result:
                logger.error("Failed to connect")
                return
                
            logger.info("Connected! Starting subscription...")
            
            # Use known good market ID
            market_id = "0x0511ddc4e6586f3bfe1acb2dd905f8b8a82c97e1edaef654b12ca7e6031ca0fa"
            
            # Create a test callback that logs everything
            def test_callback(data):
                logger.info(f"TEST CALLBACK RECEIVED: {type(data)}")
                try:
                    # Try to put something in the queue manually
                    ws_message = WebSocketMessage(
                        message_id=f"test_{int(time.time() * 1000)}",
                        message_type=MessageType.ORDERBOOK,
                        data=data,
                        market_id=market_id
                    )
                    
                    if not client._message_queue.full():
                        client._message_queue.put_nowait(ws_message)
                        logger.info("Successfully put message in queue")
                        collector.callback_calls += 1
                    else:
                        logger.warning("Queue is full!")
                        
                except Exception as e:
                    logger.error(f"Error in test callback: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Subscribe with our test callback directly
            logger.info(f"Subscribing to market {market_id}...")
            task = asyncio.create_task(
                client._client.listen_spot_orderbook_updates(
                    market_ids=[market_id],
                    callback=test_callback
                )
            )
            
            # Wait for callbacks
            logger.info("Waiting 20 seconds for callbacks...")
            await asyncio.sleep(20)
            
            logger.info(f"Callback was called {collector.callback_calls} times")
            logger.info(f"Message handler received {len(collector.messages)} messages")
            
            # Check message queue status
            queue_size = client._message_queue.qsize()
            logger.info(f"Message queue size: {queue_size}")
            
            # Check if message processor is running
            if hasattr(client, '_processing_task') and client._processing_task:
                logger.info(f"Message processor task running: {not client._processing_task.done()}")
            else:
                logger.warning("No message processor task found!")
            
            # Cancel subscription
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        except Exception as e:
            logger.error(f"Error in callback debug test: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if client.get_connection_state() == ConnectionState.CONNECTED:
                await client.disconnect()
    
    @pytest.mark.asyncio
    async def test_debug_message_processor(self):
        """Debug the message processor specifically"""
        logger.info("Starting message processor debug test...")
        
        config = WebSocketConfig()
        client = InjectiveStreamClient(config=config, network="mainnet")
        collector = CallbackDebugCollector()
        client.register_handler(collector)
        
        try:
            # Connect
            result = await client.connect()
            if not result:
                logger.error("Failed to connect")
                return
            
            # Manually put a test message in the queue
            test_message = WebSocketMessage(
                message_id="test_123",
                message_type=MessageType.ORDERBOOK,
                data={"test": "data"},
                market_id="test_market"
            )
            
            logger.info("Putting test message in queue...")
            client._message_queue.put_nowait(test_message)
            logger.info(f"Queue size after put: {client._message_queue.qsize()}")
            
            # Wait a bit for processing
            logger.info("Waiting for message processing...")
            await asyncio.sleep(2)
            
            logger.info(f"Messages processed by handler: {len(collector.messages)}")
            if collector.messages:
                msg = collector.messages[0]
                logger.info(f"Processed message: {msg.message_id} - {msg.message_type}")
            
        finally:
            if client.get_connection_state() == ConnectionState.CONNECTED:
                await client.disconnect()
