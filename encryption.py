from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, hmac, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateNumbers, RSAPublicNumbers
import os
import base64
import pickle
import hashlib
from sympy import isprime

class EncryptionNode:
    def __init__(self, username, password):
        self.username = username
        self.password = password.encode()

        # Generate deterministic symmetric key
        self.my_key = self._derive_symmetric_key()

        # Generate deterministic private/public key pair
        self.private_key, self.public_key = self._derive_key_pair()

        # Generate deterministic signature
        self.signature = self._derive_signature()

        # Connections storage
        self.connections = {}

    def _derive_symmetric_key(self):
        """Derive a symmetric key deterministically from username and password."""
        salt = hashlib.sha256(self.username.encode()).digest()  # Use username as salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,
            backend=default_backend()
        )
        return kdf.derive(self.password)

    def _derive_key_pair(self):
        """Derive a deterministic RSA key pair using HKDF and the username/password."""
        # Derive a deterministic seed from the username and password
        salt = b"key_pair_generation_salt"  # Fixed salt for key pair derivation
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"key_pair_seed",
        )
        seed = hkdf.derive(self.username.encode() + self.password)  # Combine username and password

        # Convert seed into an integer
        seed_int = int.from_bytes(seed, "big")


        def _generate_prime(seed, bits):
            state = seed
            while True:
                # Generate a candidate prime number deterministically
                state = int(hashlib.sha256(state.to_bytes((state.bit_length() + 7) // 8, "big")).hexdigest(), 16)
                candidate = state | (1 << (bits - 1)) | 1  # Ensure candidate is odd and has the required bit length
                if isprime(candidate):  # Use SymPy's isprime
                    return candidate


        # Deterministically generate the RSA primes p and q
        p = _generate_prime(seed_int, 1024)
        q = _generate_prime(seed_int + 1, 1024)  # Ensure q is different from p

        # Compute RSA key parameters
        n = p * q
        phi = (p - 1) * (q - 1)
        e = 65537  # Standard public exponent
        d = pow(e, -1, phi)  # Compute modular inverse of e

        # Construct the RSA private key
        private_numbers = RSAPrivateNumbers(
            p=p,
            q=q,
            d=d,
            dmp1=d % (p - 1),
            dmq1=d % (q - 1),
            iqmp=pow(q, -1, p),
            public_numbers=RSAPublicNumbers(e=e, n=n),
        )
        private_key = private_numbers.private_key()

        return private_key, private_key.public_key()

    def _derive_signature(self):
        """Derive a deterministic signature."""
        h = hmac.HMAC(self.my_key, hashes.SHA256(), backend=default_backend())
        h.update(self.username.encode())
        return h.finalize()

    def server_connect(self, server_name):
        """Set up a connection with the encryption node on the server."""
        shared_key = os.urandom(32)  # Generate a shared encryption key
        server_signature = os.urandom(16)  # Example signature
        self.connections[server_name] = {"shared_key": shared_key, "signature": server_signature}
        print(f"Connected to server {server_name}.")

    def exchange_keys(self, target_client, target_public_key):
        """Securely exchange public key and signature with another client."""
        # Placeholder for key exchange logic
        self.connections[target_client] = {"shared_key": os.urandom(32)}  # Example key exchange
        print(f"Exchanged keys with {target_client}.")

    def encrypt_message_with_shared_key(self, recipient, data):
        """Encrypt a message using a shared key with a recipient."""
        shared_key = self.connections.get(recipient, {}).get("shared_key")
        if not shared_key:
            raise ValueError(f"No shared key found for {recipient}.")
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(shared_key), modes.CFB(iv))
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(data.encode()) + encryptor.finalize()
        return base64.b64encode(iv + encrypted_data).decode()

    def decrypt_message_with_shared_key(self, sender, encrypted_data):
        """Decrypt a message using a shared key with a sender."""
        shared_key = self.connections.get(sender, {}).get("shared_key")
        if not shared_key:
            raise ValueError(f"No shared key found for {sender}.")
        raw_data = base64.b64decode(encrypted_data)
        iv, ciphertext = raw_data[:16], raw_data[16:]
        cipher = Cipher(algorithms.AES(shared_key), modes.CFB(iv))
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(ciphertext) + decryptor.finalize()
        return decrypted_data.decode()

    def encrypt_with_private_key(self, data):
        """Encrypt a message using the node's private key."""
        encrypted = self.public_key.encrypt(
            data.encode(),
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
        return base64.b64encode(encrypted).decode()

    def verify_message(self, message, signature, sender_public_key):
        """Verify a message signature from another client."""
        try:
            sender_public_key.verify(
                signature,
                message.encode(),
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            print("Message verified successfully.")
            return True
        except InvalidSignature:
            print("Invalid signature.")
            return False

    def save(self, filename):
        """Save the node's state to a file."""
        with open(filename, 'wb') as f:
            pickle.dump({
                'username': self.username,
                'private_key': self.private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                ),
                'public_key': self.public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                ),
                'signature': self.signature,
                'connections': self.connections,
            }, f)
        print(f"Node saved to {filename}.")

    @classmethod
    def restore(cls, filename):
        """Restore the node's state from a file."""
        with open(filename, 'rb') as f:
            data = pickle.load(f)
        private_key = serialization.load_pem_private_key(data['private_key'], password=None)
        public_key = serialization.load_pem_public_key(data['public_key'])
        node = cls(username=data['username'], private_key=private_key, public_key=public_key, signature=data['signature'])
        node.connections = data['connections']
        print(f"Node restored from {filename}.")
        return node
