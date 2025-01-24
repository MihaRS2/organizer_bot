import base64
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

class EncryptionManager:
    @staticmethod
    def encrypt_value(key_base64: str, value: str) -> str:
        logger.debug("EncryptionManager.encrypt_value called...")
        key = base64.urlsafe_b64decode(key_base64)
        f = Fernet(key)
        encrypted = f.encrypt(value.encode()).decode()
        logger.debug("Value encrypted successfully.")
        return encrypted

    @staticmethod
    def decrypt_value(key_base64: str, encrypted_value: str) -> str:
        logger.debug("EncryptionManager.decrypt_value called...")
        key = base64.urlsafe_b64decode(key_base64)
        f = Fernet(key)
        decrypted = f.decrypt(encrypted_value.encode()).decode()
        logger.debug("Value decrypted successfully.")
        return decrypted
