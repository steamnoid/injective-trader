import pytest
import asyncio
import warnings
import logging
import sys
import os
import io
from contextlib import redirect_stderr
from unittest.mock import patch

# Suppress specific warnings that are not relevant for our tests
warnings.filterwarnings("ignore", category=RuntimeWarning, message="coroutine.*was never awaited")
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*Event loop is closed")
warnings.filterwarnings("ignore", category=RuntimeWarning, message=".*Task was destroyed but it is pending")
warnings.filterwarnings("ignore", module="grpc")

# Suppress specific error messages from our code during test teardown
logging.getLogger('injective_bot.connection.injective_client').setLevel(logging.WARNING)

# Filter stderr to suppress unwanted asyncio messages
class FilteredStderr:
    def __init__(self, original_stderr):
        self.original_stderr = original_stderr
        
    def write(self, text):
        # Filter out specific unwanted messages
        unwanted_messages = [
            "error canceling timeout height sync task",
            "Task was destroyed but it is pending!",
            "Message processor error: Event loop is closed",
            "Fatal error in message processor: no running event loop",
            "task:",  # This catches all task details lines
            "wait_for=<Future",  # This catches task future details
            "coro=<InjectiveStreamClient",  # This catches our specific coroutines
            "coro=<AsyncClient",  # This catches injective SDK coroutines
        ]
        
        # Check if the text contains any unwanted messages
        for msg in unwanted_messages:
            if msg in text:
                return  # Don't write unwanted messages
                
        # Write everything else to the original stderr
        self.original_stderr.write(text)
        
    def flush(self):
        self.original_stderr.flush()
        
    def __getattr__(self, name):
        return getattr(self.original_stderr, name)

@pytest.fixture(scope="session", autouse=True)
def filter_stderr():
    """Filter stderr to suppress unwanted asyncio task messages."""
    original_stderr = sys.stderr
    sys.stderr = FilteredStderr(original_stderr)
    yield
    sys.stderr = original_stderr

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

def pytest_runtest_teardown(item):
    """Clean up after each test to prevent task leakage."""
    try:
        # Get the current event loop
        loop = asyncio.get_running_loop()
        
        # Cancel all pending tasks
        tasks = [task for task in asyncio.all_tasks(loop) if not task.done()]
        for task in tasks:
            task.cancel()
            
        # Give tasks a moment to cancel
        if tasks:
            try:
                loop.run_until_complete(
                    asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=0.1
                    )
                )
            except (asyncio.TimeoutError, RuntimeError):
                # Ignore timeout and runtime errors during cleanup
                pass
    except RuntimeError:
        # No running loop, nothing to clean up
        pass

def pytest_sessionfinish(session, exitstatus):
    """Final cleanup at the end of test session."""
    try:
        # Cancel all remaining tasks
        for task in asyncio.all_tasks():
            if not task.done():
                task.cancel()
    except RuntimeError:
        # No event loop, nothing to clean up
        pass
