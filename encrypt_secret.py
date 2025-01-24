#!/usr/bin/env python3

import sys
import base64
from cryptography.fernet import Fernet

def encrypt_value(key_base64: str, value: str) -> str:
    key = base64.urlsafe_b64decode(key_base64)
    f = Fernet(key)
    return f.encrypt(value.encode()).decode()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python encrypt_secret.py <base64_key> <secret>")
        sys.exit(1)
    
    base64_key = sys.argv[1]
    secret = sys.argv[2]

    encrypted = encrypt_value(base64_key, secret)
    print(encrypted)
