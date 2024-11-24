import socket
import uuid
import logging
from message import JsonMessage
from typing import Dict, Optional
from buffer import Buffer
import threading
import time
from encryption import EncryptionNode

class Client:
    def __init__(self, name: str, host: str, port: int, username: str = "Testing", password: str="password") -> None:
        self.name: str = name
        self.server=None
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
        self.outgoing=[]
        
        threading.Thread(target=self.handle_outgoing, daemon=True).start()
        
        self.security=EncryptionNode(username=username,password=password,logger=self.logger)
        
        self.connect()
                
        
    def handle_outgoing(self) -> None:
        while True:
            if len(self.outgoing)>0:
                
                self.lock.acquire()
                messages = self.outgoing
                self.outgoing = []
                self.lock.release()
                msg=JsonMessage(messages)
                messages=msg.split(1024,encryption= lambda x: self.security.encrypt_for_connection(self.server,x))
                for indx in messages:
                    self.client_socket.sendall(indx)
                        
            time.sleep(0.1)

    def generate_message_id(self) -> str:
        """Generates a random message ID."""
        return str(uuid.uuid4())

    def connect(self) -> None:
        """Connects to the server via the request channel."""
        try:
            self.client_socket.connect((self.server_host, self.server_port))

            private_key, public_key = self.security.initialize_connection()
            
            # Send initial connection message for the request channel
            init_message = JsonMessage({
                "channel": "request",
                "source": self.name,
                "role": "client",
                "public_key": self.security.serialize_key(public_key)
            })
            self.client_socket.sendall(init_message.serialize())
            self.lock=threading.Lock()

            # Wait for acknowledgment
            ack_data = self.client_socket.recv(1024)
            if ack_data:
                ack_message = JsonMessage.deserialize(ack_data)
                if ack_message.get("channel") == "request" and ack_message.get("source"):
                    self.logger.info(f"Successfully established request channel with {ack_message['source']}")
                    self.server=ack_message["source"]
                    other_public_key=self.security.deserialize_key(ack_message["public_key"])
                    self.security.complete_connection(other_name=self.server,other_public_key=other_public_key,\
                        connection_private_key=private_key)
                else:
                    self.logger.error("Failed to establish request channel.")
            else:
                self.logger.error("No acknowledgment received from server.")
        except Exception as e:
            self.logger.error(f"Failed to connect to server {self.server_host}:{self.server_port}: {e}")

    def send_prompt(self, message_text: Dict[str,str]) -> Optional[Dict[str,str]]:
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
            self.incoming+=1
            if self.incoming==1:
                reply_thread = threading.Thread(target=self.receive_reply)
                reply_thread.start()
            self.lock.acquire()
            self.outgoing.append(message)
            self.lock.release()
            self.logger.info(f"Sent prompt to server: {message}")
            reply=self.buffer.wait_on(message["id"],timeout=5)
            return reply            
        except Exception as e:
            self.logger.error(f"Failed to send prompt: {e}")
            return None

    def receive_reply(self) -> None:
        """Receives a reply to the prompt."""
        self.logger.info("New thread started to receive reply.")
        while self.incoming>0:
            try:
                data = self.client_socket.recv(1024)
                if data:
                    complete=self.buffer.store_data(data)
                    if complete[0]:
                        messages=JsonMessage.reassemble(complete[1],decryption=lambda x: self.security.decrypt_from_connection(self.server,x))
                    else:
                        continue
                    for message in messages:
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