from typing import Any, Dict
from server import Server
import copy
import hashlib
import threading
import random
import time

R = 2
W = 2

class HashRing:
    def __init__(self, server: str, host: str, port: int, ring = None, vtime = None, network = None, preference_list = None, vnodes = 3):
        self.ring = ring or {}   # key: server name , value: list of tuples of range of hash values
        self.vnodes = vnodes
        self.network = network or {} # key: server name, value: tuple of host and port
        self.v_time = vtime or {}
        self.preference_list = preference_list or {}
        self.add_node(server, host, port)

    def add_node(self, server: str, host, port):
        if server in self.ring:
            return
        self.v_time[server] = 1
        self.network[server] = [host, port]
        if self.ring:
            self.ring[server] = []
            segments = self.get_all_segments()
            segments.sort(key=lambda x: x[0], reverse=True)
            for i in range(self.vnodes):
                segment = segments.pop(0)
                revised_keys = [segment[1][0], (segment[1][1]+segment[1][0]-1)//2]
                added_keys = [(segment[1][1]+segment[1][0]+1)//2, segment[1][1]]
                self.ring[server].append(added_keys)
                self.ring[segment[2]].remove(segment[1])
                self.ring[segment[2]].append(revised_keys)
                self.ring[segment[2]].sort(key=lambda x: x[0])
                # here, also need to ensure that it receives the data for the keys in its storage range
                # This is JUST KEY ALLCOATION, not data transfer
        else:
            # first node is added with vnodes and hash range of 0 to 2^32, divide this range into vnode parts
            # 256 bits was getting too big, and was causing problems
            self.ring[server] = []
            for i in range(self.vnodes):
                self.ring[server].append([i*(2**32)//self.vnodes, ((i+1)*(2**32)//self.vnodes)-1])
            
    def get_all_segments(self):
        segments = []
        for key, value in self.ring.items():
            for i in range(len(value)):
                segments.append([value[i][1]-value[i][0], value[i], key])
        return segments

    def remove_node(self, server:str):
        if server not in self.ring:
            return
        # all_segments = self.get_all_segments()
        self.v_time[server] += 1
        del self.network[server]
        for i in range(self.vnodes):
            segment = self.ring[server].pop(0)
            down_node = self.get_node(segment[0]-1)
            down = None
            up_node = self.get_node(segment[1]+1)
            up = None
            if down_node:
                for keys in self.ring[down_node]:
                    if keys[1] == segment[0]-1:
                        down = keys
                        break
            if up_node:
                for keys in self.ring[up_node]:
                    if keys[0] == segment[1]+1:
                        up = keys
                        break
            if up and down:
                if int(up[1])-int(up[0]) >= int(down[1])-int(down[0]):
                    revised_keys = [down[0], segment[1]]
                    self.ring[down_node].remove(down)
                    self.ring[down_node].append(revised_keys)
                    self.ring[down_node].sort(key=lambda x: x[0])
                else:
                    revised_keys = [segment[0], up[1]]
                    self.ring[up_node].remove(up)
                    self.ring[up_node].append(revised_keys)
                    self.ring[up_node].sort(key=lambda x: x[0])
            elif up:
                revised_keys = [segment[0], up[1]]
                self.ring[up_node].remove(up)
                self.ring[up_node].append(revised_keys)
                self.ring[up_node].sort(key=lambda x: x[0])
            elif down:
                revised_keys = [down[0], segment[1]]
                self.ring[down_node].remove(down)
                self.ring[down_node].append(revised_keys)
                self.ring[down_node].sort(key=lambda x: x[0])
        # here, also need to ensure that it receives the data for the keys in its storage range
        # This is JUST KEY ALLCOATION, not data transfer
        del self.ring[server]
        

    def get_node(self, key):
        for node in self.ring:
            for segment in self.ring[node]:
                if key >= segment[0] and key <= segment[1]:
                    return node
        return None
    
    def to_dict(self):
        """Converts the HashRing into a JSON-serializable dictionary."""
        return {
            "ring": self.ring,
            "vnodes": self.vnodes,
            "v_time": self.v_time,
            "network": self.network,
        }

    @classmethod
    def from_dict(cls, data):
        """Reconstructs a HashRing object from a dictionary."""
        obj = cls(server=None, host=None, port=None)  # Create an empty instance
        obj.ring = data["ring"]
        obj.vnodes = data["vnodes"]
        obj.v_time = data["v_time"]
        obj.network = data["network"]
        return obj
    

class Dynamo(Server):
    def __init__(self, name: str, host: str = '0.0.0.0', port: int = 5000, network_id = None, seed : dict = None):
        super().__init__(name, host, port)
        self.data = {} # stores data corresponding to the keys it have
        self.network_id = network_id
        self.seed = seed
    
    def start(self) -> None:
        super().start()
        if self.seed:
            hring = HashRing.from_dict(self.connect_seed())
            ring = copy.deepcopy(hring.ring)
            network = copy.deepcopy(hring.network)
            v_time = copy.deepcopy(hring.v_time)
            self.ring = HashRing(self.name, self.host, self.port, ring, v_time, network, hring.vnodes)
            self.ring.v_time[self.seed["name"]] += 1
            # print(hring.to_dict())
            # print(self.ring.to_dict())
            self.connect_all(hring.network)
            for key in self.ring.ring[self.name]:
                reply = self.send_message({"source": self.name, "destination": hring.get_node(key[0]), "channel": "transfer", "type": "prompt", "text": "get_data", "role": "server", "data": (key,self.ring.to_dict())})
                self.logger.info(f"Received data message: {reply}")
                if reply["data"]:
                    self.data.update(reply["data"])
            # Ponder upon should we put a lock on this update - CHECK
            hring.ring = self.ring.ring
            hring.network = self.ring.network
            hring.v_time = self.ring.v_time
        else:
            self.ring = HashRing(self.name, self.host, self.port)
        
        threading.Thread(target=self._gossip_periodically, daemon=True).start()

    def connect_seed(self):
        name = self.connect_to_server(self.seed['host'], self.seed['port'])
        self.seed["name"] = name
        reply = self.send_message({"source": self.name, "destination": self.seed["name"], "channel": "transfer", "type": "prompt", "text": "seed_connect", "role": "server"})
        return reply["data"]
    
    def connect_all(self, servers) -> None:
        for server in servers:
            self.connect_to_server(servers[server][0], servers[server][1])
    
    def handle_transfer(self, message: Dict[str, Any]) -> None:
        """Handles a transfer message."""
        self.logger.info(f"Received transfer message: {message}")

        if message.get("type") == "prompt":
            if message["text"] == "seed_connect":
                self.send_message({"source": self.name, "destination": message["source"], "channel": "transfer", "type": "reply", "text": "seed_connect", "role": "server", "id": message.get("id"), "data": self.ring.to_dict()})
            elif message["text"] == "get_data":
                data = self.send_data(message["data"][0], self.data)
                for key in data:
                    self.data.pop(key)
                self.ring = HashRing.from_dict(message["data"][1])
                self.send_message({"source": self.name, "destination": message["source"], "channel": "transfer", "type": "reply", "text": "get_data", "role": "server", "id": message.get("id"), "data": data})

        if message.get("type") == "notification":
            if message["text"] == "remove_node":
                ring = copy.deepcopy(self.ring.ring)
                self.ring.remove_node(message["source"])
                for key1, key2 in ring[message["source"]]:
                    node = self.ring.get_node(key1)
                    data = self.send_data([key1, key2], message["data"])
                    reply = self.send_message({"source": self.name, "destination": node, "channel": "transfer", "type": "notification", "text": "update_data", "role": "server", "data": (data, self.ring.to_dict())})
            elif message["text"] == "update_data":
                self.ring = HashRing.from_dict(message["data"][1])
                self.data.update(message["data"][0])
        pass

    def handle_request(self, message: Dict[str, Any]) -> None:
        """Handles a request message."""
        self.logger.info(f"Received request message: {message}")
        if message.get("type") == "prompt":
            key = self.hash_calc(str(message.get("key")))
            node = self.ring.get_node(int(key))
            # print(key,"key")
            # print(self.ring.to_dict())
            # print(node,"node")
            # print(message,"message")
            if node == self.name:
                if message.get("text") == "put":
                    self.put_data(key, message.get("data"))
                    reply = {"source": self.name, "destination": message.get("source"), "channel": "request", "type": "reply", "text": "Data received", "id": message.get("id"), "role": "server"}
                    self.send_message(reply)
                elif message.get("text") == "get":
                    self.logger.info(f"Data: {self.data.get(key)}")
                    data = self.send_data([int(key), int(key)], self.data)
                    reply = {"source": self.name, "destination": message.get("source"), "channel": "request", "type": "reply", "text": "Data received", "id": message.get("id"), "role": "server", "data": data}
                    self.send_message(reply)
            else:
                original_source = copy.deepcopy(message.get("source"))
                original_id = copy.deepcopy(message.get("id"))
                message["source"] = self.name
                message["destination"] = node
                message.pop("id")
                # print(message, "message")
                reply = self.send_message(message)
                self.logger.info(f"Received reply message: {reply}")
                if reply["text"] == "Data received":
                    reply["source"] = self.name
                    reply["destination"] = original_source
                    reply["id"] = original_id
                    self.send_message(reply)
        pass

    def send_data(self, keys, data_dict):
        data = {}
        key_min, key_max = keys
        # print(self.name)
        for key, val in data_dict.items():
            # print(key, key_min, key_max)
            if int(key) >= key_min and int(key) <= key_max:
                data[key] = val
                # print("data")
                # print(key, val)
        return data
    
    def hash_calc(self, data):
        return str(int.from_bytes(hashlib.sha512(data.encode('utf-8')).digest()[:4], 'big'))
    
    def put_data(self, key, data):
        self.data[key] = data
    
    def stop(self):
        """Stops the server and closes all connections."""
        super().stop()
        if self.seed:
            self.send_message({"source": self.name, "destination": self.seed["name"], "channel": "transfer", "type": "notification", "text": "remove_node", "data": self.data})
        self.running = False
        self.server_socket.close()
        for channel_dict in [self.request_channels, self.gossip_channels, self.transfer_channels]:
            for conn in channel_dict.values():
                conn.close()
        self.logger.info(f"Server {self.name} stopped.")

    # Adding the Gossip Protocol to the Dynamo class

    # - don't need to transfer data within gossip, as we do that as and when a new node joins, or an existing node leaves

    def is_greater_eq_vtime(self, vtime1, vtime2):
        for key in vtime1.keys():
            if key in vtime2 and vtime1[key] < vtime2[key]:
                return False
        return True

    def handle_gossip(self, message: Dict[str, Any]) -> None:
        """Handles a gossip message."""
        self.logger.info(f"Received gossip message: {message}")
        if message.get("type") == "prompt":
            hash_ring_received = HashRing.from_dict(message.get("data"))
            if not self.is_greater_eq_vtime(self.ring.v_time, hash_ring_received.v_time):
                self.update_for_gossip(hash_ring_received)
                self.send_message({"source": self.name, "destination": message["source"], "channel": "gossip", "type": "reply", "text": "gossip received", "id": message.get("id"), "role": "server", "data": {}})
            else:
                self.send_message({"source": self.name, "destination": message["source"], "channel": "gossip", "type": "reply", "text": "gossip received", "id": message.get("id"), "role": "server", "data": self.ring.to_dict()})

    def update_for_gossip(self, hash_ring_received):
        for server in hash_ring_received.network.keys():
            if server not in self.ring.ring:
                self.connect_to_server(hash_ring_received.network[server][0], hash_ring_received.network[server][1])
        self.ring = hash_ring_received
    
    def _gossip_periodically(self) -> None:
        """Periodically sends gossip messages to random servers."""
        while self.running:
            try:
                if self.gossip_channels.keys():
                    random_server = random.choice(list(self.gossip_channels.keys()))
                    gossip_msg = {
                        "source": self.name,
                        "destination": random_server,
                        "channel": "gossip",
                        "type": "prompt",
                        "role": "server",
                        "text": "gossip initiated",
                        "data": self.ring.to_dict()
                    }
                    reply = self.send_message(gossip_msg)

                    if reply.get("text") == "gossip received" and reply.get("data"):
                        self.logger.info(f"Gossip successful with server {random_server}")
                        self.update_for_gossip(HashRing.from_dict(reply.get("data")))
                    elif reply.get("text") == "gossip received":
                        self.logger.info(f"Gossip successful with server {random_server}")
                
            except Exception as e:
                self.logger.error(f"Gossip error with server: {e}")

            time.sleep(1)  # Wait 1 second before the next gossip

