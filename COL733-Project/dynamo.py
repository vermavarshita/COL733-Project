from typing import Any, Dict
from server import Server
import copy
import hashlib
import threading
import random
import time

R = 2
W = 2
N = 3

class HashRing:
    def __init__(self, server: str, host: str, port: int, ring = None, vtime = None, network = None, preference_list = None, vnodes = 4):
        self.ring = ring or {} # key: server name , value: list of tuples of range of hash values
        self.vnodes = vnodes
        self.network = network or {} # key: server name, value: tuple of host and port
        self.v_time = vtime or {}
        self.preference_list = preference_list or {} # key: range of hash values, value: list of server names in preference order

    def add_node(self, server: str, host, port):
        if server in self.ring:
            return
        self.v_time[server] = 1
        self.network[server] = [host, port]
        needs_data_from = []
        if self.ring:
            self.ring[server] = []
            segments = self.get_all_segments()
            segments.sort(key=lambda x: x[0], reverse=True)
            for i in range(self.vnodes):
                segment = segments[i]
                revised_keys = [segment[1][0], (segment[1][1]+segment[1][0]-1)//2]
                added_keys = [(segment[1][1]+segment[1][0]+1)//2, segment[1][1]]
                l = len(self.preference_list[tuple(segment[1])])
                self.preference_list[tuple(added_keys)] = copy.deepcopy(self.preference_list[tuple(segment[1])])
                self.preference_list[tuple(added_keys)] = [server] + self.preference_list[tuple(added_keys)]
                self.preference_list[tuple(revised_keys)] = copy.deepcopy(self.preference_list[tuple(segment[1])])
                if l == N:
                    self.preference_list[tuple(added_keys)] = self.preference_list[tuple(added_keys)][:-1]
                    needs_data_from.append((segment[2], added_keys))
                elif l < N:
                    # print(self.preference_list, "preference_list1", server)
                    self.preference_list[tuple(revised_keys)] = self.preference_list[tuple(revised_keys)] + [server]
                    # print(self.preference_list, "preference_list1", server)
                    needs_data_from.append((segment[2], segment[1]))
                # print(self.preference_list, "preference_list2", server)
                del self.preference_list[tuple(segment[1])]
                # print(self.preference_list, "preference_list3", server)
                self.ring[server].append(added_keys)
                self.ring[server].sort(key=lambda x: x[0])
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
                self.preference_list[(i*(2**32)//self.vnodes, ((i+1)*(2**32)//self.vnodes)-1)] = [server]
        return needs_data_from
            
    def get_all_segments(self):
        segments = []
        for key, value in self.ring.items():
            for i in range(len(value)):
                segments.append([value[i][1]-value[i][0], value[i], key])
        return segments

    def remove_node(self, server:str):
        if server not in self.ring:
            return
        self.v_time[server] += 1
        del self.network[server]
        for r in self.preference_list.keys():
            if server in self.preference_list[r]:
                self.preference_list[r].remove(server)
        need_to_send_data_to = []
        need_to_remove_data_from = []
        for i in range(self.vnodes):
            segment = self.ring[server].pop(0)
            up = None
            down = None
            down_node = self.get_node(segment[0]-1)
            # print(segment, down_node, server, "segment, down_node, server")
            up_node = self.get_node(segment[1]+1)
            # print(segment, down_node, up_node, server, "segment, down_node, up_node, server")
            # print(segment, down_node, up_node, server, "segment, down_node, up_node, server")
            if down_node:
                for keys in self.ring[down_node]:
                    if keys[1] == segment[0]-1:
                        down = keys
                        break
            if up_node:
                for keys in self.ring[up_node]:
                    if keys[0] == ((segment[1]+1)%2**32):
                        up = keys
                        break
            # print(down, up, "down, up")
            if up and down:
                if int(up[1])-int(up[0]) >= int(down[1])-int(down[0]):
                    revised_keys = [down[0], segment[1]]
                    removed_keys = down
                    node = down_node
                else:
                    revised_keys = [segment[0], up[1]]
                    removed_keys = up
                    node = up_node
            elif up:
                revised_keys = [segment[0], up[1]]
                removed_keys = up
                node = up_node
            elif down:
                revised_keys = [down[0], segment[1]]
                removed_keys = down
                node = down_node
            # print(removed_keys, revised_keys, node, server, "removed_keys, revised_keys, node, server")
            for temp_node in self.preference_list[tuple(segment)]:
                if temp_node not in self.preference_list[tuple(removed_keys)]:
                    need_to_remove_data_from.append((temp_node, segment))
            for temp_node in self.preference_list[tuple(removed_keys)]:
                if temp_node not in self.preference_list[tuple(segment)]:  
                    need_to_send_data_to.append((temp_node, segment))
            self.ring[node].remove(removed_keys)
            self.ring[node].append(revised_keys)
            self.ring[node].sort(key=lambda x: x[0])
            self.preference_list[tuple(revised_keys)] = copy.deepcopy(self.preference_list[tuple(removed_keys)])
            # print(self.preference_list, "preference_list", server)
            del self.preference_list[tuple(removed_keys)]
            del self.preference_list[tuple(segment)]
        # here, also need to ensure that it receives the data for the keys in its storage range
        # This is JUST KEY ALLCOATION, not data transfer
        del self.ring[server]
        # print(need_to_send_data_to, need_to_remove_data_from, "need_to_send_data_to, need_to_remove_data_from")
        return need_to_send_data_to, need_to_remove_data_from
        

    def get_node(self, key):
        for node in self.ring:
            for segment in self.ring[node]:
                if key >= segment[0] and key <= segment[1]:
                    return node
        return None
    
    def get_nodes(self, key):
        for keys in self.preference_list.keys():
            if key >= keys[0] and key <= keys[1]:
                return self.preference_list[keys] 
        return None
    
    def to_dict(self):
        """Converts the HashRing into a JSON-serializable dictionary."""
        def serialize_preference_list(preference_list):
            return {str(key): value for key, value in preference_list.items()}
        
        return {
            "ring": self.ring,
            "vnodes": self.vnodes,
            "v_time": self.v_time,
            "network": self.network,
            "preference_list": serialize_preference_list(self.preference_list)
        }


    @classmethod
    def from_dict(cls, data):
        """Reconstructs a HashRing object from a dictionary."""
        def deserialize_preference_list(preference_list):
            return {eval(key): value for key, value in preference_list.items()}
        
        obj = cls(server=None, host=None, port=None)  # Create an empty instance
        obj.ring = data["ring"]
        obj.vnodes = data["vnodes"]
        obj.v_time = data["v_time"]
        obj.network = data["network"]
        obj.preference_list = deserialize_preference_list(data["preference_list"])
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
            preference_list = copy.deepcopy(hring.preference_list)
            self.ring = HashRing(self.name, self.host, self.port, ring, v_time, network, preference_list, hring.vnodes)
            needs_data_from = self.ring.add_node(self.name, self.host, self.port)
            self.ring.v_time[self.seed["name"]] += 1
            # print(hring.to_dict(), "hring", self.seed["name"])
            # print(self.ring.to_dict(), "self.ring", self.name)
            self.connect_all(hring.network)
            
            for server, keys in needs_data_from:
                reply = self.send_message({"source": self.name, "destination": server, "channel": "transfer", "type": "prompt", "text": "get_data", "role": "server", "data": (keys,self.ring.to_dict())})
                self.logger.info(f"Received data message: {reply}")
                if reply["data"]:
                    self.data.update(reply["data"])
            # Ponder upon should we put a lock on this update - CHECK
            hring.ring = self.ring.ring
            hring.network = self.ring.network
            hring.v_time = self.ring.v_time
            hring.preference_list = self.ring.preference_list
        else:
            self.ring = HashRing(self.name, self.host, self.port)
            self.ring.add_node(self.name, self.host, self.port)
        
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
                self.ring = HashRing.from_dict(message["data"][1])
                for key in data:
                    if self.ring.get_node(int(key)) != self.name:
                        self.data.pop(key)
                self.send_message({"source": self.name, "destination": message["source"], "channel": "transfer", "type": "reply", "text": "get_data", "role": "server", "id": message.get("id"), "data": data})

        if message.get("type") == "notification":
            if message["text"] == "remove_node":
                print(message["source"], "source", self.name)
                send ,remove = self.ring.remove_node(message["source"])
                print(send, remove, "send, remove", self.name) 
                # print(message["data"], "data1", self.name)
                for server, keys in send:
                    data = self.send_data(keys, message["data"])
                    # print(data, "data2", self.name, server,"server")
                    if server == self.name:
                        for key in data.keys():
                            self.data[key] = data[key]
                    else:
                        self.send_message({"source": self.name, "destination": server, "channel": "transfer", "type": "notification", "text": "update_data", "role": "server", "data": (data, self.ring.to_dict())})
                for server, keys in remove:
                    data = self.send_data(keys, message["data"])
                    # print(data, "data3", self.name)
                    if server == self.name:
                        for key in data.keys():
                            if key in self.data:
                                self.data.pop(key)
                    else:
                        self.send_message({"source": self.name, "destination": server, "channel": "transfer", "type": "notification", "text": "remove_data", "role": "server", "data": (data, self.ring.to_dict())})
            elif message["text"] == "update_data":
                self.ring = HashRing.from_dict(message["data"][1])
                self.data.update(message["data"][0])
            elif message["text"] == "remove_data":
                self.ring = HashRing.from_dict(message["data"][1])
                # print(message["data"][0], "data", self.name)
                for key in message["data"][0].keys():
                    self.data.pop(key)
        pass

    def handle_request(self, message: Dict[str, Any]) -> None:
        """Handles a request message."""
        self.logger.info(f"Received request message: {message}")
        if message.get("type") == "prompt":
            key = self.hash_calc(str(message.get("key")))
            nodes = self.ring.get_nodes(int(key))
            # print(nodes)
            if self.name in nodes:
                if message.get("text") == "put":
                    self.put_data(key, message.get("data"))
                    T = min(W, len(nodes))
                    original_id = copy.deepcopy(message.get("id"))
                    original_source = copy.deepcopy(message.get("source"))
                    message["source"] = self.name
                    for node in nodes:
                        try:
                            print(T)
                            if node == self.name:
                                T-=1
                                if T == 0:
                                    reply = {"source": self.name, "destination": original_source, "channel": "request", "type": "reply", "text": "Data received", "id": original_id, "role": "server"}
                                    self.send_message(reply)
                                continue
                            message.pop("id")
                            message["text"] = "put_next"
                            message["destination"] = node
                            reply = self.send_message(message)
                            if reply["text"] == "Data received":
                                T -= 1
                                # print(T)
                                if T == 0:
                                    reply = {"source": self.name, "destination": original_source, "channel": "request", "type": "reply", "text": "Data received", "id": original_id, "role": "server"}
                                    self.send_message(reply)
                                pass
                        except Exception as e:
                            pass
                elif message.get("text") == "get":
                    self.logger.info(f"Data: {self.data.get(key)}")
                    data = {}
                    T = min(R, len(nodes))
                    original_id = copy.deepcopy(message.get("id"))
                    original_source = copy.deepcopy(message.get("source"))
                    message["source"] = self.name
                    for node in nodes:
                        try:
                            if node == self.name:
                                dic = self.send_data([int(key), int(key)], self.data)
                                for d in dic.keys():
                                    if dic[d] in data:
                                        data[dic[d]] += 1
                                    else:
                                        data[dic[d]] = 1
                                    if data[dic[d]] == T:
                                        reply = {"source": self.name, "destination": original_source, "channel": "request", "type": "reply", "text": "Data received", "id": original_id, "role": "server", "data": data}
                                        self.send_message(reply)
                                        break
                                continue
                            message.pop("id")
                            message["destination"] = node
                            message["text"] = "get_next"
                            reply = self.send_message(message)
                            if reply["text"] == "Data received":
                                if reply["data"] in data:
                                    data[reply["data"]] += 1
                                else:
                                    data[reply["data"]] = 1

                                if data[reply["data"]] == T:
                                    reply = {"source": self.name, "destination": original_source, "channel": "request", "type": "reply", "text": "Data received", "id": original_id, "role": "server", "data": reply["data"]}
                                    self.send_message(reply)
                                    break
                        except Exception as e:
                            pass
                elif message.get("text") == "put_next":
                    self.put_data(key, message.get("data"))
                    reply = {"source": self.name, "destination": message["source"], "channel": "request", "type": "reply", "text": "Data received", "id": message.get("id"), "role": "server"}
                    self.send_message(reply)
                elif message.get("text") == "get_next":
                    dic = self.send_data([int(key), int(key)], self.data)
                    for d in dic.keys():
                        data = dic[d]
                    reply = {"source": self.name, "destination": message["source"], "channel": "request", "type": "reply", "text": "Data received", "id": message.get("id"), "role": "server", "data": data} 
                    self.send_message(reply)
            else:
                original_source = copy.deepcopy(message.get("source"))
                original_id = copy.deepcopy(message.get("id"))
                message["source"] = self.name
                for i in range(len(nodes)):
                    try:
                        message.pop("id")
                        message["destination"] = nodes[i]
                        # print(message, "message")
                        reply = self.send_message(message)
                        self.logger.info(f"Received reply message: {reply}")
                        if reply["text"] == "Data received":
                            reply["source"] = self.name
                            reply["destination"] = original_source
                            reply["id"] = original_id
                            self.send_message(reply)
                            break
                    except Exception as e:
                        pass
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

