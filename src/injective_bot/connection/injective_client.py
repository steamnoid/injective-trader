# Layer 2: WebSocket Connection Layer - Injective Stream Client
"""
Injective Protocol streaming client implementation using injective-py
"""

import asyncio
import logging
import json
import time
from typing import Optional, Dict, Any, List, Set, Callable
from datetime import datetime, timezone

# Import injective-py instead of websockets
from pyinjective import AsyncClient
from pyinjective.core.network import Network

from . import (
    ConnectionState, MessageType, ConnectionMetrics, WebSocketMessage,
    ConnectionError, ReconnectionError, MessageParsingError, RateLimitError,
    MessageHandler, ConnectionManager
)
from ..config import WebSocketConfig


logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Circuit breaker for connection reliability"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open
    
    def __enter__(self):
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half_open"
            else:
                raise ConnectionError("Circuit breaker is open")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Success
            self._on_success()
        elif issubclass(exc_type, self.expected_exception):
            # Expected failure
            self._on_failure()
        return False
    
    def _should_attempt_reset(self) -> bool:
        """Check if we should attempt to reset the circuit breaker"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful operation"""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self):
        """Handle failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"


class InjectiveStreamClient(ConnectionManager):
    """Injective Protocol streaming client using injective-py"""
    
    def __init__(
        self,
        config: WebSocketConfig,
        network: str = "testnet"  # "testnet" or "mainnet"
    ):
        self.config = config
        self.network = network
        
        # Connection state
        self._connection_state = ConnectionState.DISCONNECTED
        self._client: Optional[AsyncClient] = None
        self._connection_task: Optional[asyncio.Task] = None
        self._reconnection_task: Optional[asyncio.Task] = None
        
        # Message handling
        self._handlers: Dict[MessageType, List[MessageHandler]] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self._processing_task: Optional[asyncio.Task] = None
        
        # Metrics and monitoring
        self._metrics = ConnectionMetrics()
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=self.config.reconnect_delay_max,
            expected_exception=(Exception,)  # Simplified for injective-py
        )
        
        # Rate limiting
        self._message_timestamps: List[float] = []
        self._last_heartbeat: Optional[float] = None
        
        # Shutdown flag
        self._shutdown_requested = False
        
        # Subscription tracking
        self._active_subscriptions: Set[str] = set()
        self._subscription_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info(f"Initialized InjectiveStreamClient for {network}")

    async def connect(self) -> bool:
        """Establish connection to Injective Protocol using injective-py with robust networking"""
        if self._connection_state in [ConnectionState.CONNECTED, ConnectionState.CONNECTING]:
            logger.warning("Connection already established or in progress")
            return True

        self._connection_state = ConnectionState.CONNECTING
        self._metrics.connection_attempts += 1

        try:
            with self._circuit_breaker:
                # Import network utilities
                from .network_utils import NetworkConnectivityManager
                
                # Create robust client with endpoint fallback
                logger.info(f"Establishing robust connection to {self.network}...")
                self._client, node_type = await NetworkConnectivityManager.create_robust_client(
                    network=self.network,
                    max_retries=3
                )
                
                logger.info(f"✅ Connected using {node_type} node")
                
                # Test streaming capability
                streaming_ok = await NetworkConnectivityManager.test_streaming_capability(self._client)
                if not streaming_ok:
                    logger.warning("⚠️ Streaming capability limited - some operations may fail")
                
                # Update state and metrics
                self._connection_state = ConnectionState.CONNECTED
                self._metrics.successful_connections += 1
                self._metrics.connection_start_time = datetime.now(timezone.utc)

                # Start message processing
                self._processing_task = asyncio.create_task(self._message_processor())

                logger.info(f"Successfully connected to Injective Protocol ({self.network}) via {node_type}")
                return True

        except Exception as e:
            self._connection_state = ConnectionState.FAILED
            self._metrics.failed_connections += 1
            logger.error(f"Failed to connect to Injective Protocol: {e}")

            # Schedule reconnection if not shutting down
            if not self._shutdown_requested:
                await self._schedule_reconnection()

            return False

    async def disconnect(self) -> None:
        """Close connection gracefully"""
        logger.info("Disconnecting from Injective Protocol")
        self._shutdown_requested = True

        # Cancel tasks with proper exception handling
        tasks_to_cancel = []
        
        if self._reconnection_task and not self._reconnection_task.done():
            tasks_to_cancel.append(self._reconnection_task)

        if self._connection_task and not self._connection_task.done():
            tasks_to_cancel.append(self._connection_task)

        if self._processing_task and not self._processing_task.done():
            tasks_to_cancel.append(self._processing_task)

        # Cancel subscription tasks
        for subscription_id, task in self._subscription_tasks.items():
            if not task.done():
                tasks_to_cancel.append(task)

        # Cancel all tasks
        for task in tasks_to_cancel:
            task.cancel()

        # Wait for tasks to actually cancel with timeout
        if tasks_to_cancel:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                    timeout=2.0
                )
            except asyncio.TimeoutError:
                logger.warning("Some tasks did not cancel within timeout")
            except Exception as e:
                logger.debug(f"Expected exceptions during task cancellation: {e}")

        # Close client connection
        if self._client:
            # injective-py client doesn't need explicit close
            self._client = None

        # Clear subscription tracking
        self._active_subscriptions.clear()
        self._subscription_tasks.clear()

        # Update state and metrics
        self._connection_state = ConnectionState.DISCONNECTED
        if self._metrics.connection_start_time:
            connection_duration = (datetime.now(timezone.utc) - self._metrics.connection_start_time).total_seconds()
            self._metrics.uptime_seconds += connection_duration

        logger.info("Disconnected from Injective Protocol")

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """Send message - not used with injective-py streaming"""
        logger.warning("Direct message sending not supported with injective-py streaming")
        return False

    def get_connection_state(self) -> ConnectionState:
        """Get current connection state"""
        return self._connection_state

    def get_metrics(self) -> ConnectionMetrics:
        """Get connection metrics"""
        # Update real-time metrics
        if self._connection_state == ConnectionState.CONNECTED and self._metrics.connection_start_time:
            current_uptime = (datetime.now(timezone.utc) - self._metrics.connection_start_time).total_seconds()
            self._metrics.uptime_seconds = current_uptime

        return self._metrics

    def register_handler(self, handler: MessageHandler) -> None:
        """Register message handler for specific message types"""
        supported_types = handler.get_supported_message_types()

        for message_type in supported_types:
            if message_type not in self._handlers:
                self._handlers[message_type] = []
            self._handlers[message_type].append(handler)

        logger.info(f"Registered handler for message types: {supported_types}")

    async def subscribe_spot_orderbook_updates(self, market_ids: List[str]) -> None:
        """Subscribe to spot orderbook updates using single subscription for multiple markets"""
        if self._connection_state != ConnectionState.CONNECTED or not self._client:
            raise ConnectionError("Not connected to Injective Protocol")

        def orderbook_callback(data):
            """Unified callback for all markets"""
            try:
                # Extract market ID from the data
                market_id = self._extract_market_id(data)
                
                # Create WebSocket message from stream data
                ws_message = WebSocketMessage(
                    message_id=f"inj_{int(time.time() * 1000)}",
                    message_type=self._determine_message_type(data),
                    data=data,
                    market_id=market_id
                )
                
                # Put into queue without async (queue.put_nowait)
                if not self._message_queue.full():
                    self._message_queue.put_nowait(ws_message)
                    self._metrics.total_messages_received += 1
                    self._metrics.last_message_time = datetime.now(timezone.utc)
                else:
                    logger.warning("Message queue is full, dropping message")
                    
            except Exception as e:
                logger.error(f"Error in orderbook callback: {e}")

        # Single subscription for all markets (official approach)
        task = asyncio.create_task(
            self._client.listen_spot_orderbook_updates(
                market_ids=market_ids,  # All markets in single subscription
                callback=orderbook_callback
            )
        )
        
        # Store task to prevent garbage collection
        subscription_id = f"spot_orderbook_{'_'.join(market_ids[:2])}"  # Use first 2 IDs for ID
        self._subscription_tasks[subscription_id] = task
        self._active_subscriptions.add(subscription_id)
        
        logger.info(f"Subscribed to spot orderbook updates for {len(market_ids)} markets using single subscription")
        logger.info(f"Market IDs: {market_ids}")
        logger.info(f"Total active orderbook subscriptions: {len([s for s in self._active_subscriptions if 'orderbook' in s])}")

    async def subscribe_spot_trades_updates(self, market_ids: List[str]) -> None:
        """Subscribe to spot trades updates using single subscription for multiple markets"""
        if self._connection_state != ConnectionState.CONNECTED or not self._client:
            raise ConnectionError("Not connected to Injective Protocol")

        def trades_callback(data):
            """Unified callback for all markets"""
            try:
                # Extract market ID from the data
                market_id = self._extract_market_id(data)
                
                # Create WebSocket message from stream data
                ws_message = WebSocketMessage(
                    message_id=f"inj_{int(time.time() * 1000)}",
                    message_type=self._determine_message_type(data),
                    data=data,
                    market_id=market_id
                )
                
                # Put into queue without async (queue.put_nowait)
                if not self._message_queue.full():
                    self._message_queue.put_nowait(ws_message)
                    self._metrics.total_messages_received += 1
                    self._metrics.last_message_time = datetime.now(timezone.utc)
                else:
                    logger.warning("Message queue is full, dropping message")
                    
            except Exception as e:
                logger.error(f"Error in trades callback: {e}")

        # Single subscription for all markets (official approach)
        task = asyncio.create_task(
            self._client.listen_spot_trades_updates(
                market_ids=market_ids,  # All markets in single subscription
                callback=trades_callback
            )
        )
        
        # Store task to prevent garbage collection
        subscription_id = f"spot_trades_{'_'.join(market_ids[:2])}"  # Use first 2 IDs for ID
        self._subscription_tasks[subscription_id] = task
        self._active_subscriptions.add(subscription_id)
        
        logger.info(f"Subscribed to spot trades updates for {len(market_ids)} markets using single subscription")
        logger.info(f"Market IDs: {market_ids}")
        logger.info(f"Total active trades subscriptions: {len([s for s in self._active_subscriptions if 'trades' in s])}")

    async def subscribe_derivative_orderbook_updates(self, market_ids: List[str]) -> None:
        """Subscribe to derivative orderbook updates using single subscription for multiple markets"""
        if self._connection_state != ConnectionState.CONNECTED or not self._client:
            raise ConnectionError("Not connected to Injective Protocol")

        def orderbook_callback(data):
            """Unified callback for all markets"""
            try:
                # Extract market ID from the data
                market_id = self._extract_market_id(data)
                
                # Create WebSocket message from stream data
                ws_message = WebSocketMessage(
                    message_id=f"inj_{int(time.time() * 1000)}",
                    message_type=self._determine_message_type(data),
                    data=data,
                    market_id=market_id
                )
                
                # Put into queue without async (queue.put_nowait)
                if not self._message_queue.full():
                    self._message_queue.put_nowait(ws_message)
                    self._metrics.total_messages_received += 1
                    self._metrics.last_message_time = datetime.now(timezone.utc)
                else:
                    logger.warning("Message queue is full, dropping message")
                    
            except Exception as e:
                logger.error(f"Error in derivative orderbook callback: {e}")

        # Single subscription for all markets (official approach)
        task = asyncio.create_task(
            self._client.listen_derivative_orderbook_updates(
                market_ids=market_ids,  # All markets in single subscription
                callback=orderbook_callback
            )
        )
        
        # Store task to prevent garbage collection
        subscription_id = f"derivative_orderbook_{'_'.join(market_ids[:2])}"  # Use first 2 IDs for ID
        self._subscription_tasks[subscription_id] = task
        self._active_subscriptions.add(subscription_id)
        
        logger.info(f"Subscribed to derivative orderbook updates for {len(market_ids)} markets using single subscription")
        logger.info(f"Market IDs: {market_ids}")
        logger.info(f"Total active derivative subscriptions: {len([s for s in self._active_subscriptions if 'derivative' in s])}")

    async def _message_processor(self) -> None:
        """Process messages from the queue"""
        try:
            while not self._shutdown_requested:
                try:
                    # Check if event loop is still running before processing
                    loop = asyncio.get_running_loop()
                    if loop.is_closed():
                        logger.debug("Event loop is closed, stopping message processor")
                        break
                        
                    # Get message from queue with timeout
                    message = await asyncio.wait_for(
                        self._message_queue.get(),
                        timeout=1.0
                    )

                    # Process message with handlers
                    await self._dispatch_message(message)

                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    logger.debug("Message processor cancelled")
                    break
                except RuntimeError as e:
                    if "Event loop is closed" in str(e) or "no running event loop" in str(e):
                        logger.debug("Event loop closed during message processing")
                        break
                    else:
                        logger.error(f"Runtime error in message processor: {e}")
                        break
                except Exception as e:
                    # Check if this is a shutdown-related exception
                    if self._shutdown_requested or "Event loop is closed" in str(e):
                        logger.debug("Message processor stopping due to shutdown")
                        break
                    logger.error(f"Message processor error: {e}")
                    # Don't break the loop on errors, just log and continue
                    if not self._shutdown_requested:
                        await asyncio.sleep(0.1)  # Brief pause to prevent tight error loops
        except asyncio.CancelledError:
            logger.debug("Message processor task cancelled during shutdown")
        except RuntimeError as e:
            if "Event loop is closed" in str(e) or "no running event loop" in str(e):
                logger.debug("Message processor stopped - event loop closed")
            else:
                logger.error(f"Fatal runtime error in message processor: {e}")
        except Exception as e:
            logger.error(f"Fatal error in message processor: {e}")
        finally:
            logger.debug("Message processor finished")

    async def _dispatch_message(self, message: WebSocketMessage) -> None:
        """Dispatch message to registered handlers"""
        handlers = self._handlers.get(message.message_type, [])

        if not handlers:
            logger.debug(f"No handlers registered for message type: {message.message_type}")
            return

        # Dispatch to all handlers concurrently
        tasks = []
        for handler in handlers:
            task = asyncio.create_task(handler.handle_message(message))
            tasks.append(task)

        # Wait for all handlers to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _determine_message_type(self, message_data: Dict[str, Any]) -> MessageType:
        """Determine message type from injective-py stream data"""
        if "orderbook" in message_data:
            return MessageType.ORDERBOOK
        elif "trades" in message_data or "trade" in message_data:
            return MessageType.TRADES
        elif "block_height" in message_data or "block_time" in message_data:
            return MessageType.MARKET_DATA
        elif "account" in message_data or "balance" in message_data:
            return MessageType.ACCOUNT
        elif "derivative" in message_data:
            return MessageType.DERIVATIVE_MARKETS
        elif "market" in message_data:
            return MessageType.MARKET_METADATA
        elif "error" in message_data:
            return MessageType.ERROR
        else:
            return MessageType.MARKET_DATA  # Default fallback

    def _extract_market_id(self, message_data: Dict[str, Any]) -> Optional[str]:
        """Extract market ID from injective-py stream data"""
        # Try common patterns for market ID extraction
        if isinstance(message_data, dict):
            for key in ["market_id", "marketId", "market"]:
                if key in message_data:
                    return message_data[key]
            
            # Check nested structures
            for nested_key in ["orderbook", "trade", "market"]:
                if nested_key in message_data and isinstance(message_data[nested_key], dict):
                    nested_data = message_data[nested_key]
                    for key in ["market_id", "marketId", "market"]:
                        if key in nested_data:
                            return nested_data[key]
        
        return None

    def _check_rate_limit(self) -> bool:
        """Check if we're within rate limits"""
        current_time = time.time()

        # Clean old timestamps (keep only last minute)
        self._message_timestamps = [
            ts for ts in self._message_timestamps 
            if current_time - ts < 60
        ]

        # Check if we're within the rate limit
        return len(self._message_timestamps) < self.config.max_message_rate

    async def _schedule_reconnection(self) -> None:
        """Schedule reconnection with exponential backoff"""
        if self._shutdown_requested or self._reconnection_task:
            return

        self._connection_state = ConnectionState.RECONNECTING
        self._metrics.reconnection_count += 1

        # Calculate backoff delay
        delay = min(
            self.config.reconnect_delay_base * (2 ** min(self._metrics.reconnection_count, 10)),
            self.config.reconnect_delay_max
        )

        logger.info(f"Scheduling reconnection in {delay:.1f} seconds (attempt #{self._metrics.reconnection_count})")

        async def reconnect():
            try:
                await asyncio.sleep(delay)
                if not self._shutdown_requested:
                    # Check if event loop is still running
                    try:
                        loop = asyncio.get_running_loop()
                        if loop.is_closed():
                            logger.debug("Event loop closed during reconnection")
                            return
                    except RuntimeError:
                        logger.debug("No running event loop during reconnection")
                        return
                    await self.connect()
            except asyncio.CancelledError:
                logger.debug("Reconnection cancelled")
            except RuntimeError as e:
                if "Event loop is closed" in str(e):
                    logger.debug("Reconnection stopped - event loop closed")
                else:
                    logger.error(f"Runtime error during reconnection: {e}")
            except Exception as e:
                logger.error(f"Error during reconnection: {e}")

        self._reconnection_task = asyncio.create_task(reconnect())

    async def _test_connection(self) -> None:
        """Test the connection to ensure it's working"""
        if not self._client:
            raise ConnectionError("Client not initialized")
        
        # Use a simple query to test the connection
        try:
            # Try to get chain info as a basic connectivity test
            # This is a simple call that should work if connection is established
            await self._client.get_chain_id()
        except Exception as e:
            raise ConnectionError(f"Connection test failed: {e}")

    def _get_event_loop(self) -> asyncio.AbstractEventLoop:
        """Get the current event loop or create a new one if needed"""
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            # No running loop, try to get the default one
            try:
                return asyncio.get_event_loop()
            except RuntimeError:
                # No default loop, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop


__all__ = [
    "CircuitBreaker",
    "InjectiveStreamClient"
]
