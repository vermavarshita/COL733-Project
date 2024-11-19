from dynamo import Dynamo
from client import Client

server1 = Dynamo(name="Server1", host='127.0.0.1', port=8001, network_id="111")
server1.start()

client=Client(name="Client", host='127.0.0.1', port=8001)

reply = client.send_prompt({"text": "put", "data": "H"})

reply = client.send_prompt({"text": "put", "data": "Hello"})

print(server1.data, "Server1")
# print(server2.data, "Server2")


print(server1.ring.to_dict(), "Server1")
# print(server2.ring.to_dict(), "Server2")

server2 = Dynamo(name="Server2", host='127.0.0.1', port=8002, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
server2.start()

print(server1.data["10390643903460887828"], "Server1") 
print(server2.data["3897293785619054295"], "Server2")  

print(server1.ring.to_dict(), "Server1")
print(server2.ring.to_dict(), "Server2")

server1.stop()
server2.stop()
client.stop()