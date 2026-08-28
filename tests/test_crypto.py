import json
import pytest
from intermesh.crypto import generate_keypair, get_public_key_pem, encrypt_for, decrypt_with


def test_keypair_generation():
    """Vérifie la génération d'une paire RSA-2048 valide."""
    private_key = generate_keypair()
    public_pem = get_public_key_pem(private_key)
    
    assert public_pem.startswith("-----BEGIN PUBLIC KEY-----")
    assert public_pem.strip().endswith("-----END PUBLIC KEY-----")


def test_e2e_encryption_decryption_cycle():
    """Vérifie que le chiffrement hybride est 100% réversible."""
    recipient_privkey = generate_keypair()
    recipient_pubkey_pem = get_public_key_pem(recipient_privkey)
    
    secret_payload = json.dumps({"account_number": "FR7630006000011234567890189", "balance": 994000.50})
    
    # Chiffrement
    encrypted_b64 = encrypt_for(recipient_pubkey_pem, secret_payload)
    
    assert encrypted_b64 != secret_payload
    assert len(encrypted_b64) > 100
    
    # Déchiffrement
    decrypted_payload = decrypt_with(recipient_privkey, encrypted_b64)
    assert decrypted_payload == secret_payload
    
    data = json.loads(decrypted_payload)
    assert data["balance"] == 994000.50


def test_decryption_with_wrong_key_fails():
    """Vérifie qu'un tiers ne peut pas déchiffrer avec une mauvaise clé privée."""
    legit_key = generate_keypair()
    attacker_key = generate_keypair()
    
    legit_pub_pem = get_public_key_pem(legit_key)
    encrypted = encrypt_for(legit_pub_pem, "Message Ultra Confidentiel")
    
    with pytest.raises(Exception):
        decrypt_with(attacker_key, encrypted)
