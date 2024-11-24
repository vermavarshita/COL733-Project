# In-memory KeyValueStore
import random

from dynamo import Dynamo
from client import Client

server1 = Dynamo(name="Server1", host='127.0.0.1', port=8001, network_id="111")
server1.start()


# server2 = Dynamo(name="Server2", host='127.0.0.1', port=8002, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
# server2.start()



# server3 = Dynamo(name="Server3", host='127.0.0.1', port=8003, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
# server3.start()


# server4 = Dynamo(name="Server4", host='127.0.0.1', port=8004, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
# server4.start()

class KeyValueStore:
    def __init__(self,message_handler,username,password):
        self.store = {}
        self.client=Client(name="Client1", host='127.0.0.1', port=8001, message_handler=message_handler,username=username,password=password)
        
        
    def new(self):
        while True:
            key = str(random.randint(100000, 999999))
            if key not in self.store:
                return key
            elif self.store[key] == "" or self.store[key] == None:
                return key

    def get(self, key):
        reply=self.client.send_prompt({"text": "get", "key": key})
        value=reply["data"]
        return value


    def put(self, key, value):
        reply=self.client.send_prompt({"text": "put", "key": key, "data": value})
        return reply["data"]