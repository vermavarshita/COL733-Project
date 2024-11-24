from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import ec
import os
import base64
import pickle
import logging

class EncryptionNode:
    def __init__(self, username, password,logger=None):
        self.username = username
        self.password = password

        # Generate deterministic private/public key pair
        self.private_key, self.public_key = self._derive_key_pair()

        # Connections storage
        self.connections = {}
        
        self.logger = logger or logging.getLogger(__name__)

    # Serialize the public key to PEM format and return as base64 (optional)
    def serialize_key(self,public_key):
        """
        Serialize an ECPublicKey object to a base64-encoded PEM string.
        
        :param public_key: The public key (ECPublicKey) to serialize.
        :return: A base64 encoded string of the public key in PEM format.
        """
        # Serialize the public key to PEM format
        pem_public_key = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Convert PEM to base64 encoding
        base64_public_key = base64.b64encode(pem_public_key).decode('utf-8')
        
        return base64_public_key


    # Deserialize a base64 encoded PEM string back to an ECPublicKey object
    def deserialize_key(self,base64_public_key):
        """
        Deserialize a base64-encoded PEM string back to an ECPublicKey object.
        
        :param base64_public_key: A base64 encoded string of the public key in PEM format.
        :return: The deserialized ECPublicKey object.
        """
        # Decode the base64 string to get the PEM data
        pem_data = base64.b64decode(base64_public_key)

        # Deserialize the PEM data to an ECPublicKey object
        public_key = serialization.load_pem_public_key(pem_data)

        return public_key


    def _derive_key_pair(self):
        """Derive a deterministic ECC key pair using HKDF and the username/password."""
        # Derive a deterministic seed from the username and password
        salt = b"key_pair_generation_salt"  # Fixed salt for key pair derivation
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            info=b"key_pair_seed",
        )
        seed = hkdf.derive(self.username.encode() + self.password.encode())  # Combine username and password

        # Use the derived seed as a deterministic private key
        private_key = ec.derive_private_key(int.from_bytes(seed, "big"), ec.SECP256K1())

        # Generate the corresponding public key
        public_key = private_key.public_key()

        return private_key, public_key

    def initialize_connection(self):
        """
        Initializes a secure connection by generating a private key and returning the public key
        for use in the key exchange with another party.
        
        Returns:
            ec.EllipticCurvePublicKey: The public key for the other party to use in key exchange.
        """
        # Generate the private key for the connection
        private_key = ec.generate_private_key(ec.SECP256R1())  # SECP256R1 is commonly used curve
        public_key = private_key.public_key()

        self.logger.info(f"Connection initialized. Public key generated.")

        return private_key, public_key
    
    def complete_connection(self, other_public_key,other_name,connection_private_key):
        """
        Completes the secure connection by performing the key exchange with the other party's public key.
        
        Args:
            other_public_key (ec.EllipticCurvePublicKey): The public key of the other party.
        
        Returns:
            bytes: The derived shared key used for encryption.
        """
        # Perform the key exchange to compute the shared secret
        shared_secret = connection_private_key.exchange(ec.ECDH(), other_public_key)

        # Derive a shared encryption key using HKDF
        shared_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,  # AES-256 requires a 256-bit key
            salt=None,  # Optional salt; could be pre-shared or fixed
            info=b"handshake data",  # Contextual info to prevent key reuse
        ).derive(shared_secret)

        # Store the shared key and the public key of the other party
        self.connections[other_name] = {"shared_key": shared_key, "public_key": other_public_key,"private_key":connection_private_key}
        self.logger.info(f"Secure connection completed with {other_name}.")

    def encrypt_for_connection(self, recipient, data: bytes):
        """
        Encrypt data for a specific recipient using the shared key for that connection.

        Args:
            recipient (str): The recipient's name to identify the connection.
            data (str): The plaintext data to encrypt.

        Returns:
            str: The encrypted data, encoded in base64.
        """
        shared_key = self.connections[recipient]["shared_key"]
        private_key = self.connections[recipient]["private_key"]

        # Sign the data using the private ECC key
        signature = private_key.sign(
            data,
            ec.ECDSA(hashes.SHA256())
        )

        # Generate a random 16-byte IV for encryption
        iv = os.urandom(16)

        # Initialize the AES cipher in CBC mode
        cipher = Cipher(algorithms.AES(shared_key), modes.CBC(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        
        sig_len = len(signature)
        #convert sig_len to 2 bytes
        sig_len = sig_len.to_bytes(2, byteorder='big')

        # Combine the data and the signature
        data_with_signature = data + signature + sig_len

        # Pad the data to make it a multiple of the block size
        pad_length = 16 - (len(data_with_signature) % 16)
        padded_data = data_with_signature + bytes([pad_length]) * pad_length

        # Encrypt the padded data
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

        # Return IV + encrypted data as a base64-encoded string
        return base64.b64encode(iv + encrypted_data)

    def decrypt_from_connection(self, sender, data):
        """
        Decrypt data from a specific sender using the shared key for that connection.

        Args:
            sender (str): The sender's name to identify the connection.
            data (str): The encrypted data (base64 encoded).

        Returns:
            str: The decrypted plaintext data.
        """
        shared_key = self.connections[sender]["shared_key"]
        public_key = self.connections[sender]["public_key"]

        # Decode the base64-encoded data
        encrypted_data = base64.b64decode(data)

        # Extract the IV from the first 16 bytes
        iv = encrypted_data[:16]
        encrypted_data = encrypted_data[16:]

        # Initialize the AES cipher in CBC mode
        cipher = Cipher(algorithms.AES(shared_key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()

        # Decrypt the data
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

        # Remove the padding
        pad_length = decrypted_data[-1]
        data_with_signature = decrypted_data[:-pad_length]

        sig_len = int.from_bytes(data_with_signature[-2:], byteorder='big')
        
        # Extract the plaintext and the signature
        signature = data_with_signature[-(sig_len+2):-2]
        plaintext_data = data_with_signature[:-(sig_len+2)]

        # Verify the signature
        try:
            public_key.verify(
                signature,
                plaintext_data,
                ec.ECDSA(hashes.SHA256())
            )
        except Exception:
            self.logger.CRITICAL("Signature verification failed")
            return None

        return plaintext_data


    def encrypt_with_private_key(self, private_key, public_key, data,sign=True):
        """
        Encrypt a message using the recipient's public key and sign the message with the private key.

        :param private_key: The private key object used for signing.
        :param public_key: The public key object used for encrypting.
        :param data: The data to encrypt (string).
        :return: Base64 encoded string of encrypted data.
        """
        # Sign the message with the private key using ECDSA (Elliptic Curve Digital Signature Algorithm)
        if sign:
            signature = private_key.sign(
                data,
                ec.ECDSA(hashes.SHA256())
            )
        else:
            signature = b''

        sig_len = len(signature)
        sig_len = sig_len.to_bytes(2, byteorder='big')
        # Append the signature to the data
        data_with_signature = data + signature + sig_len

        # Encrypt the data with the recipient's public key (using ECIES)
        shared_key = private_key.exchange(ec.ECDH(), public_key)  # ECDH key exchange

        # Derive a symmetric encryption key from the shared secret
        encryption_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"encryption_key"
        ).derive(shared_key)

        # Generate a random nonce for AES encryption
        nonce = os.urandom(12)  # 12 bytes (96 bits) is a common size for nonce in GCM mode

        # Encrypt the data using the derived symmetric key (AES for encryption) and the generated nonce
        cipher = Cipher(algorithms.AES(encryption_key), modes.GCM(nonce))
        encryptor = cipher.encryptor()
        encrypted_data = encryptor.update(data_with_signature) + encryptor.finalize()

        # Get the authentication tag
        tag = encryptor.tag

        # Return base64 encoded encrypted data (including nonce and tag at the beginning)
        return base64.b64encode(nonce + tag + encrypted_data)


    def decrypt_with_private_key(self, private_key, public_key, encrypted_data_b64):
        """
        Decrypt the message using the recipient's private key and verify the signature.

        :param private_key: The private key object used for decryption.
        :param public_key: The public key object used for verification.
        :param encrypted_data_b64: The base64 encoded encrypted data (including nonce and tag).
        :return: Decrypted message (string).
        """
        # Decode the base64 encoded encrypted data
        encrypted_data = base64.b64decode(encrypted_data_b64)

        # Extract the nonce (first 12 bytes), tag (next 16 bytes), and encrypted message
        nonce = encrypted_data[:12]
        tag = encrypted_data[12:28]  # 16 bytes for the tag
        encrypted_message = encrypted_data[28:]

        # Decrypt the data using the derived symmetric key and the nonce
        shared_key = private_key.exchange(ec.ECDH(), public_key)  # ECDH key exchange
        encryption_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"encryption_key"
        ).derive(shared_key)

        cipher = Cipher(algorithms.AES(encryption_key), modes.GCM(nonce, tag))
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(encrypted_message) + decryptor.finalize()
        
        sig_len = int.from_bytes(decrypted_data[-2:], byteorder='big')
        
        # Extract the plaintext and the signature
        signature = decrypted_data[-(sig_len+2):-2]
        data = decrypted_data[:-(sig_len+2)]

        # Verify the signature (optional but recommended)
        try:
            if sig_len > 0:
                public_key.verify(signature, data, ec.ECDSA(hashes.SHA256()))
            # Return the decrypted message
            return data
        except Exception:
            self.logger.CRITICAL("Signature verification failed")
            return None

    def generate_ecc_private_key_from_hash_and_private_key(hash_value, existing_private_key):
        """
        Generate a deterministic ECC private key from a given SHA256 hash
        and an existing private key.

        :param hash_value: The SHA256 hash as bytes (length must be 32 bytes).
        :param existing_private_key: The existing ECC private key (used as part of the derivation process).
        :return: The generated ECC private key.
        """
        if len(hash_value) != 32:
            raise ValueError("Hash must be a 32-byte SHA256 hash.")
        
        # Derive some shared secret from the existing private key
        shared_secret = existing_private_key.private_numbers().private_value.to_bytes(32, "big")
        
        # Combine the shared secret and hash to create a new key seed
        combined_data = shared_secret + hash_value

        # Use a KDF to stretch the combined data to a suitable seed for ECC key generation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # Length of derived key material
            salt=b"deterministic-salt",
            iterations=100000,
            backend=default_backend()
        )
        seed = kdf.derive(combined_data)

        # Convert the seed to an integer and create an ECC private key from it
        private_key = ec.derive_private_key(seed, ec.SECP256R1(), default_backend())

        return private_key


    def save(self, filename):
        """Save the node's state to a file."""
        with open(filename, 'wb') as f:
            pickle.dump({
                'connections': self.connections,
            }, f)
        self.logger.info(f"Node saved to {filename}.")

    def restore(self, filename):
        """Restore the node's state from a file."""
        with open(filename, 'rb') as f:
            data = pickle.load(f)
        self.connections = data['connections']
        self.logger.info(f"Node restored from {filename}.")
