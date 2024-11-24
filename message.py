from __future__ import annotations
import json
from typing import Final, Any, Optional
import uuid
import base64

class JsonMessage:
    def __init__(self, msg: dict[str, Any]) -> None:
        self._msg_d: Final[dict[str, Any]] = msg

    @staticmethod
    def deserialize(msg: bytes) -> JsonMessage:
        # Extract and decode the JSON message
        msg_str = msg.decode('utf-8')
        len_ = len(msg_str)
        if len_==0:
            return JsonMessage({})
        msg_json: dict[str, Any] = json.loads(msg_str)
        return JsonMessage(msg=msg_json)

    def generate_message_id(self) -> str:
        """Generates a random message ID."""
        return str(uuid.uuid4())

    @property
    def msg_bytes(self) -> bytes:
        return str(self).encode()

    @property
    def msg_len(self) -> int:
        return len(self.msg_bytes)

    def serialize(self) -> bytes:
        """
        -------------------------------------------------------------
        | message-length (8-bytes) | message (message-length bytes) |
        -------------------------------------------------------------
        length:- is unsigned is integer.
        message:- is utf-8 encoded
        """
        return self.msg_bytes

    def __str__(self) -> str:
        return json.dumps(self._msg_d)

    def __getitem__(self, key: str) -> Any:
        return self._msg_d[key]

    def __setitem__(self, key: str, val: Any) -> None:
        self._msg_d[key] = val

    def __contains__(self, key: str) -> bool:
        return key in self._msg_d 
        
    def get(self, key: str) -> Optional[Any]:
        return self._msg_d.get(key)

    def pop(self, key: str) -> Optional[Any]:
        return self._msg_d.pop(key)
    
    def split(self, size: int = 1024, encryption : function = lambda x: x) -> list[bytes]:
        """
        Splits the message into chunks of specified size.

        :param size: The total size of each serialized chunk (including metadata).
        :return: List of serialized message chunks.
        """
        messages = []
        data = encryption(self.msg_bytes)
        message_id = self.generate_message_id()
        
        # Define chunk metadata format
        format_dict = {"id": message_id, "order": 1024, "length": 1024, "data": ""}
        format_msg = JsonMessage(format_dict)
        empty = format_msg.serialize()
        # Calculate the chunk data size
        chunk_size = size - len(empty)  # Leave space for metadata and delimiters
        imflation_factor = 4/3
        chunk_size = int(chunk_size/imflation_factor)
        num_chunks = (len(data) + chunk_size - 1) // chunk_size

        # Create chunks
        for i, start in enumerate(range(0, len(data), chunk_size)):
            chunk = data[start:start + chunk_size]
            format_dict["order"] = i
            format_dict["data"] = base64.b64encode(chunk).decode('utf-8')
            format_dict["length"] = num_chunks
            format_msg = JsonMessage(format_dict)
            serialized = format_msg.serialize()
            # add padding
            serialized += b" " * (size - len(serialized))
            messages.append(serialized)

        return messages

    def reassemble(messages: list[tuple[int,bytes]],decryption : function = lambda x:x) -> JsonMessage:
        """
        Reassembles the original message from serialized chunks.

        :param messages: List of serialized message chunks.
        :return: Reassembled JsonMessage object.
        """
        # Sort chunks by their order
        messages.sort(key=lambda x: x[0])
        
        full_message = b""
        for _, chunk in messages:
            full_message += base64.b64decode(chunk)
        full_message = decryption(full_message)
        return JsonMessage.deserialize(full_message)