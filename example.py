from server import Server
from client import Client

server1 = Server(name="Server1", host='127.0.0.1', port=8001)
server1.start()

server2 = Server(name="Server2", host='127.0.0.1', port=8002)
server2.start()

server1.network_id="111"
server2.network_id="111"

# Connect server1 to server2
server1.connect_to_server(host='127.0.0.1', port=8002)

reply=server1.send_message({"source": "Server1", "destination": "Server2", "channel": "request", "type": "prompt", "text": "Hello on request channel"})
server2.send_message({"source": "Server2", "destination": "Server1", "channel": "gossip", "type": "notification", "text": "Hello on gossip channel"})
server1.send_message({"source": "Server1", "destination": "Server2", "channel": "transfer", "type": "notification", "text": "Hello on transfer channel"})

print("Reply received outside:", reply)


client=Client(name="Client", host=server1.host, port=server1.port)

reply=client.send_prompt({"text": "Hello on request channel from client"})

print("Reply received outside:", reply)

server1.stop()
server2.stop()
client.stop()