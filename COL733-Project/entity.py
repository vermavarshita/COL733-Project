from node import Node

class Entity(Node):
    def __init__(self, client):
        super().__init__()
        self.dict = {}
        self.client = client
        self.attributes = []
    
        
    def set(self, name, value):
        if not name in self.attributes:
            raise KeyError(f"Attribute {name} not allowed")
        if name in self.dict:
            key = self.dict[name]
            node=Node()
            node.set_data(value)
            node.store(key, self.client, 100)
        else:
            key = self.client.new()
            self.dict[name] = key
            node=Node()
            node.set_data(value)
            node.store(key, self.client, 100)
        
    def get(self, name):
        if not name in self.attributes:
            raise KeyError(f"Attribute {name} not allowed")
        if not name in self.dict:
            raise KeyError(f"Attribute {name} not found")
        
        key = self.dict[name]
        data=Node.get_data(key, self.client)
        return data
    
    def save(self,key):
        self.set_data(self.dict)
        self.store(key, self.client, 100)
        return key
    
    def load(self,key, client):
        data=Node.get_data(key, client)
        self.dict=data
    
    