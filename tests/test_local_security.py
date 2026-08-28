import os
import pytest
from intermesh.crypto import generate_keypair, get_private_key_pem, save_encrypted_vault, load_encrypted_vault


def test_encrypted_local_key_vault(tmp_path):
    """Vérifie que la clé privée est chiffrée sur disque et récupérable avec la passphrase."""
    vault_file = os.path.join(tmp_path, "vault.json")
    passphrase = "my_ultra_secure_local_passphrase_2026"

    # 1. Générer une clé privée
    priv_key = generate_keypair()
    original_pem = get_private_key_pem(priv_key)

    # 2. Sauvegarder dans le coffre-fort chiffré (PBKDF2 + AES-256-GCM)
    save_encrypted_vault(vault_file, original_pem, passphrase)

    # 3. Vérifier que le fichier n'est PAS en clair sur le disque
    with open(vault_file, "r") as f:
        content = f.read()
        assert "BEGIN PRIVATE KEY" not in content
        assert "PBKDF2" or "ciphertext" in content

    # 4. Charger et déchiffrer avec la bonne passphrase
    restored_pem = load_encrypted_vault(vault_file, passphrase)
    assert restored_pem == original_pem

    # 5. Tentative de déchiffrement avec un mauvais mot de passe
    with pytest.raises(Exception):
        load_encrypted_vault(vault_file, "wrong_password")

    print("✅ Local Key Vault encryption & PBKDF2 test passed!")


if __name__ == "__main__":
    test_encrypted_local_key_vault(os.path.expanduser("/tmp"))
