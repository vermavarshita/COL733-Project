from server import Server
import time

server1=Server("server1",host="localhost",port=8080,network_id=1)
server1.start()

server2=Server("server2",host="localhost",port=8081,network_id=1)
server2.start()

server1.connect_to_server("localhost",8081)

#string of length 2000
test_string="a"*10

for _ in range(10):
    server1.send_message({"source": "server1", "destination": "server2", "channel": "request", "type": "notification", "text": "put", "role": "server", "data": test_string})
    time.sleep(0.01)

reply=server1.send_message({"source": "server1", "destination": "server2", "channel": "request", "type": "prompt", "text": "put", "role": "server", "data": test_string})

print(reply)

server1.stop()
server2.stop()