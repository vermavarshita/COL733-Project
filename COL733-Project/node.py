import pickle
import json
class Node:
    def __init__(self):
        self.data = None
        self.extension = []
    
    def set_data(self, data):
        data_type= "STR" if type(data)==str else "JSN"
        if data_type=="JSN":
            data=json.dumps(data)
        self.data = data+data_type
        
    def store(self, key, client,size):
        # break the data into chunks of given size
        data=[self.data[i:i+size] for i in range(0, len(self.data), size)]
        Nodes=[]
        if len(self.extension)<len(data):
            for i in range(len(data)-len(self.extension)):
                self.extension.append(client.new())
        
        for i in range(len(self.extension)):
            node=Node()
            if i<len(self.extension):
                node.data=data[i]
            else:
                node.data=""
            Nodes.append(node)
        
        for i in range(len(Nodes)):
            Nodes[i].put(self.extension[i],client)
            
        self.data="Taken"
        self.put(key,client)
            
    def put(self, key, client):
        self.binary_data = self.encode()
        client.put(key, self.binary_data)
        
    def encode(self):
        # encode the data and extension
        return pickle.dumps((self.data, self.extension))
    
    def decode(binary_data,client):
        # decode the data and extension
        data, extension = pickle.loads(binary_data)
        node = Node()
        if extension:
            data=""
            for key in extension:
                ext=Node.decode(client.get(key),client)
                data+=ext.data
        node.data=data
        node.extension = extension
        return node
    
    def get_data(key, client):
        node = Node.decode(client.get(key),client)
        data=node.data
        if data[-3:]=="STR":
            data=data[:-3]
        else:
            data=json.loads(data[:-3])
        return data             
        