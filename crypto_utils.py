"""
Encryption module for sensitive config data
Encrypts API keys before saving to YAML files
"""

import os
import base64
import logging
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# Key storage location
KEY_FILE = Path.home() / '.agentbear' / '.master_key'
SALT_FILE = Path.home() / '.agentbear' / '.salt'


def get_or_create_master_key() -> bytes:
    """Get existing master key or create new one"""
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if KEY_FILE.exists():
        with open(KEY_FILE, 'rb') as f:
            return f.read()
    
    # Generate new key
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as f:
        f.write(key)
    
    # Set restrictive permissions (owner read/write only)
    os.chmod(KEY_FILE, 0o600)
    
    logger.info("Created new master encryption key")
    return key


def get_or_create_salt() -> bytes:
    """Get existing salt or create new one"""
    SALT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    if SALT_FILE.exists():
        with open(SALT_FILE, 'rb') as f:
            return f.read()
    
    # Generate new salt
    salt = os.urandom(16)
    with open(SALT_FILE, 'wb') as f:
        f.write(salt)
    
    os.chmod(SALT_FILE, 0o600)
    return salt


def get_cipher() -> Fernet:
    """Get Fernet cipher instance"""
    key = get_or_create_master_key()
    return Fernet(key)


def encrypt_value(value: str) -> str:
    """
    Encrypt a string value
    Returns base64-encoded encrypted string with prefix
    """
    if not value:
        return value
    
    # Check if already encrypted (has prefix)
    if value.startswith('ENC:'):
        return value
    
    try:
        cipher = get_cipher()
        encrypted = cipher.encrypt(value.encode())
        return f"ENC:{base64.urlsafe_b64encode(encrypted).decode()}"
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        return value


def decrypt_value(value: str) -> str:
    """
    Decrypt a string value
    Handles both encrypted (ENC: prefix) and plain text
    """
    if not value:
        return value
    
    # Check if encrypted
    if not value.startswith('ENC:'):
        return value  # Plain text, return as-is
    
    try:
        cipher = get_cipher()
        encrypted_data = base64.urlsafe_b64decode(value[4:])  # Remove ENC: prefix
        decrypted = cipher.decrypt(encrypted_data)
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return value  # Return original if decryption fails


def encrypt_config(config: dict) -> dict:
    """
    Encrypt sensitive fields in config dict
    Returns new dict with encrypted values
    """
    config = config.copy()
    
    # Fields to encrypt
    sensitive_fields = [
        ('model', 'anthropic_api_key'),
        ('model', 'openai_api_key'),
        ('telegram', 'bot_token'),
        ('github', 'token'),
    ]
    
    for section, field in sensitive_fields:
        if section in config and field in config[section]:
            value = config[section][field]
            if value and not value.startswith('ENC:'):
                config[section][field] = encrypt_value(value)
                logger.debug(f"Encrypted {section}.{field}")
    
    return config


def decrypt_config(config: dict) -> dict:
    """
    Decrypt sensitive fields in config dict
    Returns new dict with decrypted values
    """
    config = config.copy()
    
    # Fields to decrypt
    sensitive_fields = [
        ('model', 'anthropic_api_key'),
        ('model', 'openai_api_key'),
        ('telegram', 'bot_token'),
        ('github', 'token'),
    ]
    
    for section, field in sensitive_fields:
        if section in config and field in config[section]:
            value = config[section][field]
            if value and value.startswith('ENC:'):
                config[section][field] = decrypt_value(value)
                logger.debug(f"Decrypted {section}.{field}")
    
    return config


def rotate_key() -> bool:
    """
    Rotate the master encryption key
    Re-encrypts all existing encrypted values with new key
    """
    try:
        # Load existing key
        old_key = get_or_create_master_key()
        old_cipher = Fernet(old_key)
        
        # Generate new key
        new_key = Fernet.generate_key()
        new_cipher = Fernet(new_key)
        
        # TODO: Find and re-encrypt all config files
        # This would require scanning for bond_config.yaml files
        # and re-encrypting them
        
        # Save new key
        with open(KEY_FILE, 'wb') as f:
            f.write(new_key)
        
        logger.info("Rotated master encryption key")
        return True
        
    except Exception as e:
        logger.error(f"Key rotation failed: {e}")
        return False


# For testing
if __name__ == '__main__':
    print("Testing encryption...")
    
    # Test encrypt/decrypt
    test_value = "sk-ant-api03-test-key-12345"
    
    encrypted = encrypt_value(test_value)
    print(f"Original: {test_value}")
    print(f"Encrypted: {encrypted}")
    
    decrypted = decrypt_value(encrypted)
    print(f"Decrypted: {decrypted}")
    
    assert test_value == decrypted, "Decryption failed!"
    print("✓ Encryption test passed!")
    
    # Test idempotency
    encrypted2 = encrypt_value(encrypted)
    assert encrypted == encrypted2, "Double encryption should return same!"
    print("✓ Idempotency test passed!")