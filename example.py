from dynamo import Dynamo
from client import Client
from time import sleep

server1 = Dynamo(name="Server1", host='127.0.0.1', port=8001, network_id="111")
server1.start()

# client=Client(name="Client", host='127.0.0.1', port=8001)

# reply = client.send_prompt({"text": "put", "key": 25, "data": "H"})

# reply = client.send_prompt({"text": "put", "key": 50, "data": "Hello"})
# print(reply, "Client")

# print(server1.data, "Server1")
# print(server2.data, "Server2")


print(server1.ring.to_dict(), "Server1")
# print(server2.ring.to_dict(), "Server2")

server2 = Dynamo(name="Server2", host='127.0.0.1', port=8002, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
server2.start()

print(server1.ring.to_dict(), "Server1")

server3 = Dynamo(name="Server3", host='127.0.0.1', port=8003, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
server3.start()

print(server1.ring.to_dict(), "Server1")

server4 = Dynamo(name="Server4", host='127.0.0.1', port=8004, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
server4.start()

# print(server1.data, "Server1") 
# print(server2.data, "Server2") 
# print(server3.data, "Server3") 
# reply = client.send_prompt({"text": "get", "key": 50})
# print(reply, "Client")

print(server1.ring.to_dict(), "Server1")
print(server2.ring.to_dict(), "Server2")
print(server3.ring.to_dict(), "Server3")
print(server4.ring.to_dict(), "Server4")
sleep(5)
print("slept")
print(server1.ring.to_dict(), "Server1")
print(server2.ring.to_dict(), "Server2")
print(server3.ring.to_dict(), "Server3")
print(server4.ring.to_dict(), "Server4")

server1.stop()
server2.stop()
server3.stop()
server4.stop()
# client.stop()