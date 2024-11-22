import socket
import uuid
import logging
from message import JsonMessage
from typing import Dict
from buffer import Buffer
import threading

class Client:
    def __init__(self, name: str, host: str, port: int) -> None:
        self.name: str = name
        self.server_host: str = host
        self.server_port: int = port
        self.client_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        file_handler = logging.FileHandler(f"{name}.log")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.propagate = False
        
        self.logger.info(f"Logging started for {name}")
        
        self.buffer = Buffer(logger=self.logger)
        
        self.incoming=0
        self.source=None
        
        self.connect()

    def generate_message_id(self) -> str:
        """Generates a random message ID."""
        return str(uuid.uuid4())

    def connect(self) -> None:
        """Connects to the server via the request channel."""
        try:
            self.client_socket.connect((self.server_host, self.server_port))

            # Send initial connection message for the request channel
            init_message = JsonMessage({
                "channel": "request",
                "source": self.name,
                "role": "client"
            })
            self.client_socket.sendall(init_message.serialize())

            # Wait for acknowledgment
            ack_data = self.client_socket.recv(1024)
            if ack_data:
                ack_message = JsonMessage.deserialize(ack_data)
                if ack_message.get("channel") == "request" and ack_message.get("source"):
                    self.logger.info(f"Successfully established request channel with {ack_message['source']}")
                    self.server=ack_message["source"]
                else:
                    self.logger.error("Failed to establish request channel.")
            else:
                self.logger.error("No acknowledgment received from server.")
        except Exception as e:
            self.logger.error(f"Failed to connect to server {self.host}:{self.port}: {e}")

    def send_prompt(self, message_text: Dict[str,str]) -> None:
        """Sends a prompt message to the server."""
        try:
            message = {
                "source": self.name,
                "destination": self.server,  # This should be the server name you're sending to
                "channel": "request",
                "type": "prompt",
                "id": self.generate_message_id()
            }
            message.update(message_text)
            msg = JsonMessage(message)
            self.incoming+=1
            if self.incoming==1:
                reply_thread = threading.Thread(target=self.receive_reply)
                reply_thread.start()
            self.client_socket.sendall(msg.serialize())
            self.logger.info(f"Sent prompt to server: {message}")
            reply=self.buffer.wait_on(message["id"],timeout=5)
            return reply            
        except Exception as e:
            self.logger.error(f"Failed to send prompt: {e}")

    def receive_reply(self) -> None:
        """Receives a reply to the prompt."""
        self.logger.info("New thread started to receive reply.")
        while self.incoming>0:
            try:
                data = self.client_socket.recv(1024)
                if data:
                    message = JsonMessage.deserialize(data)
                    if message.get("type") == "reply":
                        self.logger.info(f"Received reply from server: {message}")
                        self.buffer.add(message)
                    else:
                        self.logger.critical("Received unexpected message type.")
                    self.incoming-=1
                    self.logger.info(f"Remaining incoming messages: {self.incoming}")
                else:
                    self.logger.critical("No reply received.")
            except Exception as e:
                self.logger.critical(f"Failed to receive reply: {e}")

    def disconnect(self) -> None:
        """Closes the connection to the server."""
        try:
            self.client_socket.close()
            self.logger.info("Connection closed.")
        except Exception as e:
            self.logger.error(f"Failed to close connection: {e}")
            
    def stop(self) -> None:
        self.disconnect()
        self.incoming=0
        self.logger.info("Client stopped.")