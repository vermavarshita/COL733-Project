from entity import Entity

class User(Entity):
    def __init__(self, client):
        super().__init__(client)
        self.attributes = ['username', 'password', 'friends','outgoing','incoming']
        

class Message(Entity):
    def __init__(self, client):
        super().__init__(client)
        self.attributes = ['to','from','content','timestamp']
        
class Friend(Entity):
    def __init__(self, client):
        super().__init__(client)
        self.attributes = ['username', 'key','public_key',"chat"]
        
class Chat(Entity):
    def __init__(self, client):
        super().__init__(client)
        self.attributes= ["messages"]