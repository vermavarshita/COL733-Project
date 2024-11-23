import socket
import threading
import uuid
from typing import Dict, Any
from message import JsonMessage
from buffer import Buffer
from abc import abstractmethod
import logging

class Server():
    def __init__(self, name: str, host: str = '0.0.0.0', port: int = 5000,network_id:int=0) -> None:
        self.name: str = name
        self.host: str = host
        self.port: int = port
        self.server_socket: socket.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.running: bool = False

        # Connection dictionaries
        self.request_channels: Dict[str, socket.socket] = {}
        self.gossip_channels: Dict[str, socket.socket] = {}
        self.transfer_channels: Dict[str, socket.socket] = {}    
        
        self.network_id=network_id 
        
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        file_handler = logging.FileHandler(f"{name}.log")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.logger.propagate=False
        
        self.logger.info(f"Logging started for {name}")  
        
        self.buffer = Buffer(logger=self.logger)

    def generate_message_id(self) -> str:
        """Generates a random message ID."""
        return str(uuid.uuid4())

    def handle_request(self, message: Dict[str, Any]) -> None:
        """Handles a transfer message."""
        self.logger.info(f"Received request message: {message}")
        if message.get("type") == "prompt":
            reply = {"source": self.name, "destination": message.get("source"), "channel": "request", "type": "reply", "text": f"Hello on request channel. You sent a message of length {len(message['data'])}", "id": message.get("id"), "role": "server"}
            self.send_message(reply)

    def handle_gossip(self, message: Dict[str, Any]) -> None:
        """Handles a gossip message."""
        self.logger.info(f"Received gossip message: {message}")
        if message.get("type") == "prompt":
            reply = {"source": self.name, "destination": message.get("source"), "channel": "gossip", "type": "reply", "text": f"Hello on request channel. You sent a message of length {len(message['data'])}", "id": message.get("id"), "role": "server"}
            self.send_message(reply)

    def handle_transfer(self, message: Dict[str, Any]) -> None:
        """Handles a transfer message."""
        self.logger.info(f"Received transfer message: {message}")
        if message.get("type") == "prompt":
            reply = {"source": self.name, "destination": message.get("source"), "channel": "transfer", "type": "reply", "text": f"Hello on request channel. You sent a message of length {len(message['data'])}", "id": message.get("id"), "role": "server"}
            self.send_message(reply)

    def start(self) -> None:
        """Starts the server and listens for incoming connections."""
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        self.logger.info(f"Server {self.name} started on {self.host}:{self.port}")
        threading.Thread(target=self._accept_connections, daemon=True).start()

    def _accept_connections(self) -> None:
        """Accepts incoming connections."""
        try:
            while self.running:
                client_socket, client_address = self.server_socket.accept()
                threading.Thread(
                    target=self._handle_incoming_connection, args=(client_socket,), daemon=True
                ).start()
        except:
            self.logger.error(f"Server {self.name} is down.")

    def _handle_incoming_connection(self, client_socket: socket.socket) -> None:
        """Handles a new incoming connection."""
        try:
            data = client_socket.recv(1024)
            if data:
                message = JsonMessage.deserialize(data)
                channel_type = message.get("channel")
                server_name = message.get("source")
                role = message.get("role")

                ack_message = JsonMessage({"source": self.name, "channel": channel_type, "destination": server_name, "type": "notification", "role": "server"})
                if role == "client":
                    assert channel_type == "request", "Client must connect on request channel."
                else:
                    network_id = message.get("network_id")
                    assert network_id == self.network_id, "Network ID must match."
                if channel_type == "request":
                    self.request_channels[server_name] = client_socket
                    client_socket.sendall(ack_message.serialize())
                    self.logger.info(f"Request channel established with {server_name}")
                    self._handle_request_channel(client_socket)
                elif channel_type == "gossip":
                    self.gossip_channels[server_name] = client_socket
                    client_socket.sendall(ack_message.serialize())
                    self.logger.info(f"Gossip channel established with {server_name}")
                    self._handle_gossip_channel(client_socket)
                elif channel_type == "transfer":
                    self.transfer_channels[server_name] = client_socket
                    client_socket.sendall(ack_message.serialize())
                    self.logger.info(f"Transfer channel established with {server_name}")
                    self._handle_transfer_channel(client_socket)
        except Exception as e:
            self.logger.error(f"Error handling incoming connection: {e}")
        finally:
            client_socket.close()
            
    def _handle_request_channel(self, client_socket: socket.socket) -> None:
        """Handles incoming messages on the request channel."""
        while self.running:
            try:
                data = client_socket.recv(1024)
                if data:
                    complete=self.buffer.store_data(data)
                    if complete[0]:
                        message=JsonMessage.reassemble(complete[1])
                    else:
                        continue
                    type = message.get("type")
                    if type == "reply":
                        self.buffer.add(message)
                    else:
                        request_thread = threading.Thread(target=self.handle_request, args=(message,), daemon=True)
                        request_thread.start()
            except Exception as e:
                self.logger.critical(f"Error handling request channel: {e}")
            
    def _handle_gossip_channel(self, client_socket: socket.socket) -> None:
        """Handles incoming messages on the gossip channel."""
        while self.running:
            try:
                data = client_socket.recv(1024)
                if data:
                    complete=self.buffer.store_data(data)
                    if complete[0]:
                        message=JsonMessage.reassemble(complete[1])
                    else:
                        continue
                    type = message.get("type")
                    if type == "reply":
                        self.buffer.add(message)
                    else:
                        gossip_thread = threading.Thread(target=self.handle_gossip, args=(message,), daemon=True)
                        gossip_thread.start()
            except Exception as e:
                self.logger.critical(f"Error handling gossip channel: {e}")
            
    def _handle_transfer_channel(self, client_socket: socket.socket) -> None:
        """Handles incoming messages on the transfer channel."""
        while self.running:
            try:
                data = client_socket.recv(1024)
                if data:
                    complete=self.buffer.store_data(data)
                    if complete[0]:
                        message=JsonMessage.reassemble(complete[1])
                    else:
                        continue
                    if message.get("type") == "reply":
                        self.buffer.add(message)
                    else:
                        transfer_thread = threading.Thread(target=self.handle_transfer, args=(message,), daemon=True)
                        transfer_thread.start()
            except Exception as e:
                self.logger.critical(f"Error handling transfer channel: {e}")
            
    def connect_to_server(self, host: str, port: int) -> None:
        """Connects to another server and sets up three channels."""
        try:
            temp_channels = {}
            for channel_type in ["request", "gossip", "transfer"]:
                client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client_socket.connect((host, port))

                # Send initial connection message
                init_message = JsonMessage({
                    "channel": channel_type,
                    "source": self.name,
                    "type": "notification",
                    "role": "server",
                    "network_id": self.network_id
                })
                client_socket.sendall(init_message.serialize())

                # Receive acknowledgment message with the server name
                ack_data = client_socket.recv(1024)
                if not ack_data:
                    raise ConnectionError("Did not receive acknowledgment from server.")

                ack_message = JsonMessage.deserialize(ack_data)
                remote_server_name = ack_message["source"]
                self.logger.info(f"Received acknowledgment from {remote_server_name} on {channel_type} channel.")

                # Store the connection temporarily by channel type
                temp_channels[channel_type] = client_socket

            # Move channels to appropriate dictionaries
            self.request_channels[remote_server_name] = temp_channels["request"]
            self.gossip_channels[remote_server_name] = temp_channels["gossip"]
            self.transfer_channels[remote_server_name] = temp_channels["transfer"]
            
            # Start threads to handle incoming messages
            request_thread = threading.Thread(target=self._handle_request_channel, args=(temp_channels["request"],), daemon=True)
            request_thread.start()
            gossip_thread = threading.Thread(target=self._handle_gossip_channel, args=(temp_channels["gossip"],), daemon=True)
            gossip_thread.start()
            transfer_thread = threading.Thread(target=self._handle_transfer_channel, args=(temp_channels["transfer"],), daemon=True)
            transfer_thread.start()

            self.logger.info(f"Connected to server {remote_server_name} at {host}:{port}")
            return remote_server_name
        except Exception as e:
            self.logger.error(f"Failed to connect to server {host}:{port}: {e}")
            return None

    def send_message(self, message: Dict[str,str]) -> None:
        """Sends a message through a specific channel."""
        channel = message.get("channel")
        server_name = message.get("destination")
        
        channel_dict = {
            "request": self.request_channels,
            "gossip": self.gossip_channels,
            "transfer": self.transfer_channels,
        }

        if channel not in channel_dict:
            self.logger.critical("Invalid channel.")
            return
        
        type = message.get("type")
        if type not in ["prompt", "notification", "reply"]:
            self.logger.critical("Invalid message type.")
            return
        if type == "reply" and "id" not in message:
            self.logger.critical("Reply message must have an ID.")
            return
        elif type != "reply":
            message["id"] = self.generate_message_id()

        channels = channel_dict[channel]
        if server_name not in channels:
            self.logger.critical(f"No connection to {server_name} on {channel} channel.")
            return

        try:
            socket_conn = channels[server_name]
            msg = JsonMessage(message)
            messages=msg.split(1024)
            for indx in messages:
                socket_conn.sendall(indx)                
            self.logger.info(f"Sent {message} to {server_name} on {channel} channel.")
        except Exception as e:
            self.logger.critical(f"Failed to send message to {server_name} on {channel} channel: {e}")
            
        if type == "prompt":
            reply=self.buffer.wait_on(msg["id"], timeout=2)

            if reply:
                self.logger.info(f"Reply received: {reply}")
            return reply
        else:
            return None

    def stop(self) -> None:
        """Stops the server and closes all connections."""
        self.running = False
        self.server_socket.close()
        for channel_dict in [self.request_channels, self.gossip_channels, self.transfer_channels]:
            for conn in channel_dict.values():
                conn.close()
        self.logger.info(f"Server {self.name} stopped.")
        
    def close_all_connections_to_server(self, server_name: str) -> None:
        """Closes all connections (request, gossip, transfer) to a specific server."""
        channels = {
            "request": self.request_channels,
            "gossip": self.gossip_channels,
            "transfer": self.transfer_channels,
        }

        for channel_name, channel_dict in channels.items():
            if server_name in channel_dict:
                try:
                    channel_dict[server_name].close()
                    del channel_dict[server_name]
                    self.logger.info(f"Closed {channel_name} channel with {server_name}")
                except Exception as e:
                    self.logger.critical(f"Failed to close {channel_name} channel with {server_name}: {e}")

        self.logger.info(f"All connections to {server_name} closed.")
