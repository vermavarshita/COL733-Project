from dynamo import Dynamo
from client import Client
from time import sleep

server1 = Dynamo(name="Server1", host='127.0.0.1', port=8001, network_id="111")
server1.start()

client=Client(name="Client", host='127.0.0.1', port=8001)

reply = client.send_prompt({"text": "put", "key": 25, "data": "H"})

reply = client.send_prompt({"text": "put", "key": 50, "data": "Hello"})
print(reply, "Client")

# print(server1.data, "Server1")
# print(server2.data, "Server2")


# print(server1.ring.to_dict(), "Server1")
# print(server2.ring.to_dict(), "Server2")

server2 = Dynamo(name="Server2", host='127.0.0.1', port=8002, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
server2.start()

# print(server1.ring.to_dict(), "Server1")

server3 = Dynamo(name="Server3", host='127.0.0.1', port=8003, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
server3.start()

# print(server1.ring.to_dict(), "Server1")

server4 = Dynamo(name="Server4", host='127.0.0.1', port=8004, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
server4.start()

server5 = Dynamo(name="Server5", host='127.0.0.1', port=8005, network_id="111", seed= {"host":'127.0.0.1', "port":8001})
server5.start()

# print(server1.data, "Server1") 
# print(server2.data, "Server2") 
# print(server3.data, "Server3") 
# reply = client.send_prompt({"text": "get", "key": 50})
# print(reply, "Client")

# print(server1.ring.to_dict(), "Server1")
# print(server2.ring.to_dict(), "Server2")
# print(server3.ring.to_dict(), "Server3")
# print(server4.ring.to_dict(), "Server4")

# server1.stop()
# server2.stop()
# print(server1.ring.to_dict(), "Server1")
sleep(2)
# print(server1.ring.to_dict(), "Server1")
# print("Emptying Server2")
# print(server1.ring.to_dict(), "Server1")
# print(server1.data, "server1")
# print(server3.ring.to_dict(), "Server3")
# print(server3.data, "server3")
# print(server4.ring.to_dict(), "Server4")
# print(server4.data, "server4")

# reply = client.send_prompt({"text": "put", "key": 50, "data": "Hello"})
# print(reply, "Client")

print(server1.data, "Server1")
print(server2.data, "Server2")
print(server3.data, "Server3")
print(server4.data, "Server4")
print(server5.data, "Server5")

server3.stop()
print("3 gone")
print(server1.data, "Server1")
print(server2.data, "Server2")
print(server4.data, "Server4")
print(server5.data, "Server5")
# client.
sleep(2)
server4.stop()
print("4 gone")
print(server1.data, "Server1")
print(server2.data, "Server2")
print(server5.data, "Server5")
sleep(2)
server5.stop()
print("5 gone")
print(server1.data, "Server1")
print(server2.data, "Server2")
sleep(2)
server2.stop()
print("2 gone")
print(server1.data, "Server1")
server1.stop()
client.stop()

# [[268435456, 536870911], [1342177280, 1610612735], [2415919104, 2684354559], [3489660928, 3758096383]]
# (268435456, 536870911)': ['Server3', 'Server1', 'Server2']
# (134217728, 536870911): ['Server5', 'Server1', 'Server2']

# [805306368, 1073741823], [1879048192, 2147483647], [2952790016, 3221225471], [4026531840, 4294967295]
# ['Server4', 'Server2', 'Server1'], ['Server4', 'Server2', 'Server1'], ['Server4', 'Server2', 'Server1'], ['Server4', 'Server2', 'Server1']
# ['Server1', 'Server2'], ['Server1', 'Server2'], 
