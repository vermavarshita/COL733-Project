# In-memory KeyValueStore
import random

class KeyValueStore:
    def __init__(self):
        self.store = {}
        
    def new(self):
        while True:
            key = str(random.randint(1000, 9999))
            if key not in self.store:
                return key
            elif self.store[key] == "" or self.store[key] == None:
                return key

    def get(self, key):
        value=self.store.get(key)
        # print(f"Retrieved {key} => {value}")
        return value


    def put(self, key, value):
        self.store[key] = value
        # print(f"Stored {key} => {value}")