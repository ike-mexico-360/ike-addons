# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

import base64
import hashlib
from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import logging
import os

# ENCRYPTION_KEY = os.environ.get('ODOO_ENCRYPTION_KEY_AES256')


class CustomEncryptionUtility(models.Model):
    _name = 'custom.encryption.utility'
    _description = 'Custom Encryption Utility'

    def _get_encryption_key(self):
        """
        Generates a 32-byte key from the defined constant
        """
        encrypt_key = self.env['ir.config_parameter'].sudo().get_param('database.encrypt.key')
        return hashlib.sha256(encrypt_key.encode('utf-8')).digest()

    def encrypt_aes256(self, plaintext):
        """
        Encrypts a text using AES256 in CBC mode

        Args:
            plaintext (str): Text to encrypt

        Returns:
            str: Encrypted text in base64
        """
        try:
            if not plaintext:
                return plaintext

            # Get the encryption key
            key = self._get_encryption_key()

            # Generate a random 16-byte IV
            iv = get_random_bytes(16)

            # Create the cipher object
            cipher = AES.new(key, AES.MODE_CBC, iv)

            # Apply padding to the text
            padded_text = pad(plaintext.encode('utf-8'), AES.block_size)

            # Encrypt
            encrypted = cipher.encrypt(padded_text)

            # Combine IV + encrypted data and encode in base64
            result = base64.b64encode(iv + encrypted).decode('utf-8')

            return result

        except Exception as e:
            return plaintext

    def decrypt_aes256(self, encrypted_text):
        """
        Decrypts a text encrypted with AES256

        Args:
            encrypted_text (str): Text encrypted in base64

        Returns:
            str: Decrypted text
        """
        try:
            if not encrypted_text:
                return encrypted_text

            # Get the encryption key
            key = self._get_encryption_key()

            # Decode from base64
            encrypted_data = base64.b64decode(encrypted_text.encode('utf-8'))

            # Extract IV (first 16 bytes)
            iv = encrypted_data[:16]

            # Extract encrypted data
            encrypted = encrypted_data[16:]

            # Create the cipher object
            cipher = AES.new(key, AES.MODE_CBC, iv)

            # Decrypt
            decrypted = cipher.decrypt(encrypted)

            # Remove padding
            result = unpad(decrypted, AES.block_size).decode('utf-8')

            return result

        except Exception as e:
            return encrypted_text
