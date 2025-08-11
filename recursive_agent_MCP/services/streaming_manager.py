import asyncio
from asyncio import Queue
from contextlib import asynccontextmanager
from concurrent.futures import Future

from langchain_core.callbacks.base import BaseCallbackHandler

# =====================================================================
#  Implement proper queue-based streaming
# =====================================================================
class StreamingManager:
    def __init__(self, max_queue_size: int = 100):
        self.queue = Queue(maxsize=max_queue_size)
        self.done_event = asyncio.Event()

    @asynccontextmanager
    async def stream_handler(self):
        try:
            yield self
        finally:
            self.done_event.set()

    async def put_token(self, token: str):
        if token is None:  # Sentinel for shutdown
            self.done_event.set()
            return
        try:
            await asyncio.wait_for(self.queue.put(token), timeout=1.0)
        except asyncio.TimeoutError:
            # Could add logging here to track dropped tokens
            # logger.warning(f"Dropped token due to backpressure: {token[:20]}...")
            pass

    async def stream_tokens(self):
        while not self.done_event.is_set() or not self.queue.empty():
            try:
                token = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                yield token
            except asyncio.TimeoutError:
                # Only check done_event if queue is empty
                if self.queue.empty() and self.done_event.is_set():
                    break
                continue


# =====================================================================
#  Base Token Callback for Thread-Safe Streaming
# =====================================================================

class BaseTokenCallback(BaseCallbackHandler):
    """Base callback for token streaming with proper thread safety.
    
    This class handles the async/sync boundary safely by:
    1. Capturing the event loop from the main thread
    2. Checking loop status before submission
    3. Handling futures properly without blocking
    4. Tracking errors and dropped tokens for reporting
    """
    
    def __init__(self, stream_mgr: StreamingManager, event_loop: asyncio.AbstractEventLoop, phase: str = "unknown"):
        self.stream_mgr = stream_mgr
        self.event_loop = event_loop
        self.phase = phase
        
        # Error tracking
        self.error_count = 0
        self.dropped_tokens = []
        self.stats = {
            'sent': 0,
            'dropped': 0,
            'cancelled': 0,
            'errors': 0
        }
        self.last_error = None
        
    def on_llm_new_token(self, token: str, **kwargs):
        """Called from LangChain's worker thread."""
        # Check if loop is still running
        if self.event_loop.is_closed():
            # Can't deliver token - collect for reporting
            self.dropped_tokens.append(token)
            self.stats['dropped'] += 1
            return
            
        # Submit the coroutine to the event loop
        try:
            future = asyncio.run_coroutine_threadsafe(
                self.stream_mgr.put_token(token),
                self.event_loop
            )
            self.stats['sent'] += 1
            
            # Add callback to handle result without blocking
            future.add_done_callback(self._handle_token_result)
            
        except Exception as e:
            # Future creation itself failed
            self.error_count += 1
            self.stats['errors'] += 1
            self.last_error = str(e)
            
    def _handle_token_result(self, future: Future):
        """Handle the result of token delivery (called in main thread)."""
        try:
            future.result()  # This will raise if put_token failed
        except asyncio.CancelledError:
            # Token delivery was cancelled - normal during cleanup
            self.stats['cancelled'] += 1
        except asyncio.TimeoutError:
            # Queue was full - token dropped
            self.stats['dropped'] += 1
        except Exception as e:
            # Real error - token wasn't delivered
            self.error_count += 1
            self.stats['errors'] += 1
            self.last_error = str(e)
    
    def on_llm_end(self, response, **kwargs):
        """Called when LLM finishes generating."""
        # Signal completion by sending None (sentinel)
        if not self.event_loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(
                    self.stream_mgr.put_token(None),  # This sets done_event
                    self.event_loop
                )
            except Exception as e:
                self.error_count += 1
                self.last_error = f"Failed to signal completion: {str(e)}"
            
    def get_error_summary(self) -> str:
        """Get a summary of any streaming issues."""
        if self.error_count == 0 and self.stats['dropped'] == 0:
            return ""
            
        parts = []
        if self.error_count > 0:
            parts.append(f"{self.error_count} errors")
        if self.stats['dropped'] > 0:
            parts.append(f"{self.stats['dropped']} dropped")
        if self.stats['cancelled'] > 0:
            parts.append(f"{self.stats['cancelled']} cancelled")
            
        summary = f"⚠️ {self.phase} streaming issues: {', '.join(parts)}"
        if self.last_error:
            summary += f" (last error: {self.last_error})"
            
        return summary
