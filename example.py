from server import Server
from dynamo import Dynamo
from client import Client

server1 = Dynamo(name="Server1", host='127.0.0.1', port=8001, network_id="111")
server1.start()

server2 = Dynamo(name="Server2", host='127.0.0.1', port=8002, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
server2.start()

# Connect server1 to server2
# server1.connect_to_server(host='127.0.0.1', port=8002)

# reply=server1.send_message({"source": "Server1", "destination": "Server2", "channel": "request", "type": "prompt", "text": "Hello on request channel"})
# server2.send_message({"source": "Server2", "destination": "Server1", "channel": "gossip", "type": "notification", "text": "Hello on gossip channel"})
# server1.send_message({"source": "Server1", "destination": "Server2", "channel": "transfer", "type": "notification", "text": "Hello on transfer channel"})

print("Reply received outside:", reply)


client=Client(name="Client", host=server1.host, port=server1.port)

reply=client.send_prompt({"text": "Hello on request channel from client"})

print("Reply received outside:", reply)

server1.stop()
server2.stop()
client.stop()