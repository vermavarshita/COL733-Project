from encryption import EncryptionNode

node = EncryptionNode("user1", "password")
node.server_connect("server1")
encrypted_message = node.encrypt_message_with_shared_key("server1", "Hello Server")
print("Encrypted Message:", encrypted_message)

decrypted_message = node.decrypt_message_with_shared_key("server1", encrypted_message)
print("Decrypted Message:", decrypted_message)