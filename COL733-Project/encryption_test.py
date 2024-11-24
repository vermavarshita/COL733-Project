import unittest
from cryptography.hazmat.primitives.asymmetric import ec
from encryption import EncryptionNode

class TestEncryptionNode(unittest.TestCase):

    def setUp(self):
        """Set up test users with known credentials."""
        self.node_a = EncryptionNode("Alice", "password123")
        self.node_b = EncryptionNode("Bob", "securepass456")

    def test_initialization(self):
        """Test that nodes initialize correctly with deterministic keys."""
        self.assertIsNotNone(self.node_a.private_key)
        self.assertIsNotNone(self.node_a.public_key)

        self.assertIsNotNone(self.node_b.private_key)
        self.assertIsNotNone(self.node_b.public_key)

    def test_rsa_key_pair_derivation(self):
        """Test that RSA keys are deterministically derived."""
        node_c = EncryptionNode("Alice", "password123")
        self.assertEqual(
            self.node_a.private_key.private_numbers(),
            node_c.private_key.private_numbers()
        )
        self.assertEqual(
            self.node_a.public_key.public_numbers(),
            node_c.public_key.public_numbers()
        )

    def test_connection_initialization(self):
        """Test that connection initialization generates valid keys."""
        private_key_a, public_key_a = self.node_a.initialize_connection()
        self.assertIsInstance(private_key_a, ec.EllipticCurvePrivateKey)
        self.assertIsInstance(public_key_a, ec.EllipticCurvePublicKey)

    def test_secure_connection(self):
        """Test secure connection establishment and key exchange."""
        # Initialize connections
        private_a, public_a = self.node_a.initialize_connection()
        private_b, public_b = self.node_b.initialize_connection()

        # Complete the handshake
        self.node_a.complete_connection(public_b, "Bob", private_a)
        self.node_b.complete_connection(public_a, "Alice", private_b)

        # Verify shared keys match
        self.assertEqual(
            self.node_a.connections["Bob"]["shared_key"],
            self.node_b.connections["Alice"]["shared_key"]
        )

    def test_encryption_and_decryption(self):
        """Test that data encryption and decryption work correctly."""
        private_a, public_a = self.node_a.initialize_connection()
        private_b, public_b = self.node_b.initialize_connection()

        # Complete handshake
        self.node_a.complete_connection(public_b, "Bob", private_a)
        self.node_b.complete_connection(public_a, "Alice", private_b)

        # Encrypt and decrypt data
        original_message = b"Hello, Bob!"
        encrypted_message = self.node_a.encrypt_for_connection("Bob", original_message)
        decrypted_message = self.node_b.decrypt_from_connection("Alice", encrypted_message)

        self.assertEqual(original_message, decrypted_message)

    def test_rsa_encryption_decryption(self):
        """Test RSA-based encryption and decryption."""
        message = b"Secure message"
        encrypted_message = self.node_a.encrypt_with_private_key(
            self.node_a.private_key,
            self.node_b.public_key,
            message
        )
        decrypted_message = self.node_b.decrypt_with_private_key(
            self.node_b.private_key,
            self.node_a.public_key,
            encrypted_message
        )
        self.assertEqual(message, decrypted_message)

    def test_state_save_and_restore(self):
        """Test saving and restoring node state."""
        filename = "test_node.pkl"
        self.node_a.save(filename)

        # Modify node state
        self.node_a.connections["Bob"] = {"shared_key": b"dummy_key", "public_key": None}

        # Restore state
        self.node_a.restore(filename)
        self.assertNotIn("Bob", self.node_a.connections)

    def test_signature_verification_failure(self):
        """Test that tampered data fails signature verification."""
        private_a, public_a = self.node_a.initialize_connection()
        private_b, public_b = self.node_b.initialize_connection()

        # Complete handshake
        self.node_a.complete_connection(public_b, "Bob", private_a)
        self.node_b.complete_connection(public_a, "Alice", private_b)

        # Encrypt data and tamper with it
        original_message = b"Hello, Bob!"
        encrypted_message = self.node_a.encrypt_for_connection("Bob", original_message)
        tampered_message = encrypted_message[:-1] + b"A"

        with self.assertRaises(ValueError):
            self.node_b.decrypt_from_connection("Alice", tampered_message)

if __name__ == "__main__":
    unittest.main()
