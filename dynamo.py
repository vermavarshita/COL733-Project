from typing import Any, Dict
from server import Server
import hashlib

class HashRing:
    def __init__(self, server: str, host: str, port: int, ring = None, network = None, vnodes = 4):
        self.ring = ring or {}   # key: server name , value: list of tuples of range of hash values
        self.vnodes = vnodes
        self.network = network or {} # key: server name, value: tuple of host and port
        self.add_node(server, host, port, vnodes)

    def add_node(self, host, port, server: str, vnodes:int = 4):
        if server in self.ring:
            return
        if self.ring:
            self.network[server] = (host, port) 
            self.ring[server] = []
            segments = self.get_all_segments()
            segments.sort(key=lambda x: x[0], reverse=True)
            for i in range(vnodes):
                segment = segments.pop(0)
                revised_keys = (segment[1][0], (segment[1][1]+segment[1][0]-1)//2)
                added_keys = ((segment[1][1]+segment[1][0]+1)//2, segment[1][1])
                self.ring[server].append(added_keys)
                self.ring[segment[2]].remove(segment[1])
                self.ring[segment[2]].append(revised_keys)
                sorted(self.ring[segment[2]], key=lambda x: x[0])
                # here, also need to ensure that it receives the data for the keys in its storage range
                # This is JUST KEY ALLCOATION, not data transfer
        else:
            # first node is added with vnodes and hash range of 0 to 2^256, divide this range into vnode parts
            self.ring[server] = []
            for i in range(vnodes):
                self.ring[server].append((i*(2**256)//vnodes, ((i+1)*(2**256)//vnodes)-1))
            
    def get_all_segments(self):
        segments = []
        for key, value in self.ring.items():
            for i in range(len(value)):
                segments.append((value[i][1]-value[i][0], value[i], key))
        return segments

    def remove_node(self, server:str, vnodes:int = 4):
        if server not in self.ring:
            return
        all_segments = self.get_all_segments()
        del self.network[server]
        for i in range(vnodes):
            segment = self.ring[server].pop(0)
            for j in range(len(all_segments)):
                if all_segments[j][1][0] == segment[1]+1:
                    up = all_segments.pop(j)
                if all_segments[j][1][1] == segment[0]-1:
                    down = all_segments.pop(j)
            if up[0] >= down[0]:
                revised_keys = (down[1][0], segment[1])
                self.ring[down[2]].remove(down[1])
                self.ring[down[2]].append(revised_keys)
                sorted(self.ring[down[2]], key=lambda x: x[0])
            else:
                revised_keys = (segment[0], up[1][1])
                self.ring[up[2]].remove(up[1])
                self.ring[up[2]].append(revised_keys)
                sorted(self.ring[up[2]], key=lambda x: x[0])
        # here, also need to ensure that it receives the data for the keys in its storage range
        # This is JUST KEY ALLCOATION, not data transfer
        del self.ring[server]
        

    def get_node(self, key):
        for node in self.ring:
            for segment in self.ring[node]:
                if key >= segment[0] and key <= segment[1]:
                    return node
        return None
    

class Dynamo(Server):
    def __init__(self, name: str, host: str = '0.0.0.0', port: int = 5000, network_id = None, seed : dict = None):
        super().__init__(name, host, port)
        self.data = {} # stores data corresponding to the keys it have
        self.network_id = network_id

        if seed:
            hring = self.connect_seed(seed)
            self.ring = HashRing(self.name, self.host, self.port, hring.ring, hring.network, hring.vnodes)
            self.connect_all(hring.network)
            for key in self.ring.ring[self.name]:
                reply = self.send_message({"source": self.name, "destination": hring.get_node(key[0]), "channel": "transfer", "type": "prompt", "text": "get_data", "data": (key,self.ring)})
                self.data.update(reply["data"])

        else:
            self.ring = HashRing(self.name, self.host, self.port)

    def connect_seed(self, seed: dict):
        name = self.connect_to_server(seed['host'], seed['port'])
        reply = self.send_message({"source": self.name, "destination": name, "channel": "transfer", "type": "prompt", "text": "seed_connect", "role": "server"})
        return reply["data"]
    
    def connect_all(self, servers) -> None:
        for server in servers:
            self.connect_to_server(servers[server][0], servers[server][1])
    
    def handle_transfer(self, message: Dict[str, Any]) -> None:
        """Handles a transfer message."""
        self.logger.info(f"Received transfer message: {message}")
        if message.get("type") == "prompt":
            if message["text"] == "seed_connect":
                self.send_message({"source": self.name, "destination": message["source"], "channel": "transfer", "type": "reply", "text": "seed_connect", "data": self.ring})
            elif message["text"] == "get_data":
                data = self.send_data(message["data"][0])
                self.ring = message["data"][1]
                self.send_message({"source": self.name, "destination": message["source"], "channel": "transfer", "type": "reply", "text": "get_data", "data": data})
        pass

    def handle_request(self, message: Dict[str, Any]) -> None:
        """Handles a request message."""
        self.logger.info(f"Received request message: {message}")
        if message.get("type") == "prompt":
            if message.get("text") == "put":
                self.put_data(message.get("data"))
                reply = {"source": self.name, "destination": message.get("source"), "channel": "request", "type": "reply", "text": "Data received", "id": message.get("id"), "role": "server"}
                self.send_message(reply)
        pass

    def send_data(self, keys):
        data = {}
        key_min, key_max = keys
        for key, val in self.data.items():
            if key >= key_min and key <= key_max:
                data[key] = val
                del self.data[key]
        return data
    
    def put_data(self, data):
        self.data[int(hashlib.sha256(data.encode('utf-8')).hexdigest(),16)] = data
        pass