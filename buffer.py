import threading
from typing import Dict, Any, Optional
import logging

class Buffer:
    def __init__(self,logger:Optional[logging.Logger]=None) -> None:
        # A dictionary to store the waiting threads and their associated data (e.g., events or values).
        self.waiting_threads: Dict[str, threading.Event] = {}
        self.replies: Dict[str, Any] = {}
        self.logger = logger or logging.getLogger(__name__)

    def wait_on(self, id: str, timeout: Optional[float] = 0) -> Any:
        """
        Pauses the calling thread and stores the thread context in the buffer.
        Waits until a reply is added with the matching ID or the timeout is reached.
        
        :param timeout: Timeout period in seconds. If None, waits indefinitely.
        :return: The reply if received, None if timeout occurs.
        """

        # Create an event that will be used to pause and resume the thread
        event = threading.Event()
        self.waiting_threads[id] = event
        self.logger.info(f"Waiting for a reply for ID {id}")
        

        # Wait for the event to be set (i.e., for the reply to come in)
        event_was_set = event.wait(timeout)  # timeout is in seconds, None means no timeout

        # If event is not set, return None indicating a timeout
        if not event_was_set:
            self.logger.info(f"Waiting for ID {id} timed out")
            self.waiting_threads.pop(id)
            return None

        # Once the event is set, return the reply that was associated with this ID
        reply = self.replies.get(id)
        
        # Clean up by removing the entry from the waiting dictionary
        self.waiting_threads.pop(id)
        return reply

    def add(self, reply: Dict[str,str]) -> None:
        """
        Adds the reply for the given ID and resumes the waiting thread.
        """
        id = reply.get("id")
        if id in self.waiting_threads:
            # Set the event to resume the thread
            event = self.waiting_threads[id]
            event.set()

            # Store the reply in the replies dictionary
            self.replies[id] = reply
            self.logger.info(f"Reply added for ID {id}")
        else:
            self.logger.warning(f"No thread waiting for ID {id}")
