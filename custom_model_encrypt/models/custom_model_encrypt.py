# -- coding: utf-8 --

import base64
import hashlib
import random
import string
import unicodedata

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from Crypto.Hash import SHA256

from odoo import models, fields, api, Command, _
from odoo.tools import config, ormcache


class CustomModelEncryption(models.AbstractModel):
    _name = 'custom.model.encryption'
    _description = 'Model Encryption'

    name = fields.Char(encrypt=True)

    x_name_search_ids = fields.One2many(
        'custom.model.encryption.search.helper.rel', 'encrypt_model_id',
        domain=[('field_name', '=', 'name')])

    # === COMPUTE === #
    def _compute_display_name(self):
        fnames = self._x_get_encrypt_fields()
        field_names = [x['name'] for x in fnames]
        name_is_encrypted = 'name' in field_names
        if name_is_encrypted:
            for rec in self:
                rec.display_name = self.x_decrypt_aes256(rec.name)
        else:
            super()._compute_display_name()

    # === OVERRIDE === #
    def _valid_field_parameter(self, field, name):
        """allow encryption params"""
        return name in [
            'encrypt',
            'encrypt_search_limit',
        ] or super()._valid_field_parameter(field, name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            fnames = self._x_get_encrypt_fields()

            for fname in fnames:
                field_name = fname['name']
                if fname['name'] in vals:
                    value = vals[field_name]
                    # Encrypt
                    vals[field_name] = self.x_encrypt_aes256(value)
                    # Create Hints
                    if field_name == 'name' or fname.get('limit'):
                        helper_field_name = self._x_get_search_helper_field_name(field_name)
                        if helper_field_name not in self._fields:
                            continue
                        vals[helper_field_name] = self._x_get_search_helper_data(fname, value)

        return super().create(vals_list)

    def write(self, vals):
        fnames = self._x_get_encrypt_fields()

        for fname in fnames:
            field_name = fname['name']
            if fname['name'] in vals:
                value = vals[field_name]
                # Encrypt
                vals[field_name] = self.x_encrypt_aes256(value)
                # Create Hints
                if field_name == 'name' or fname.get('limit'):
                    helper_field_name = self._x_get_search_helper_field_name(field_name)
                    if helper_field_name not in self._fields:
                        continue

                    # Remove Previous
                    rel_ids = getattr(self, helper_field_name)
                    to_delete = []
                    helper = rel_ids.encrypt_helper_id
                    for rel_id in rel_ids:
                        helper_ids = rel_id.search_read([
                            ('encrypt_helper_id', '=', rel_id.encrypt_helper_id.id)
                        ], ['id'], limit=2)
                        if len(helper_ids) == 1:
                            to_delete.append(rel_id.encrypt_helper_id.id)
                    rel_ids.unlink()
                    helper.browse(to_delete).unlink()
                    # Add News
                    vals[helper_field_name] = self._x_get_search_helper_data(fname, value)

        super().write(vals)

    def read(self, fields=None, load='_classic_read'):
        records = super().read(fields, load)

        fnames = self._x_get_encrypt_fields()

        for record in records:
            for fname in fnames:
                field_name = fname['name']
                if field_name in fields:
                    record[field_name] = self.x_decrypt_aes256(record[field_name])

        return records

    @api.model
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        fnames = self._x_get_encrypt_fields()
        field_names = [x['name'] for x in fnames]
        codes = self._x_get_encryption_search_codes()
        for i, item in enumerate(domain):
            if isinstance(item, list) or isinstance(item, tuple):
                if len(item) == 3:
                    field_name = item[0]
                    value = item[2]

                    if field_name == 'display_name':
                        field_name = 'name'

                    if field_name in field_names:
                        helper_field_name = self._x_get_search_helper_field_name(field_name)
                        if helper_field_name not in self._fields:
                            continue

                        fname = next((x for x in fnames if x['name'] == field_name), None)
                        if not fname or not (fname['name'] == 'name' or fname.get('limit')):
                            continue

                        if fname.get('limit'):
                            limit_start = fname['limit'][0]
                            limit_end = fname['limit'][1]
                            value = item[2][limit_start:limit_end]

                        domain[i] = [
                            helper_field_name + '.encrypt_helper_id.name',
                            '=',
                            self.x_encrypt_aes256_helper(self._x_get_normalized_text(value))
                        ]
                        blanks = 0
                        if isinstance(value, str):
                            blanks = value.count(' ')
                        if blanks:
                            domain.append((
                                helper_field_name + '.encrypt_helper_id.code',
                                '=',
                                codes[blanks]
                            ))
                        domain.append((
                            helper_field_name + '.encrypt_helper_id.code',
                            'not in',
                            codes[-4:],
                        ))

        return super().search_fetch(domain, field_names, offset, limit, order)

    # === PUBLIC METHODS === #
    def action_reprocess_search_helpers(self):
        fnames = self._x_get_encrypt_fields()
        for rec in self:
            data = {}
            for fname in fnames:
                if not (fname['name'] or fname.get('limit')):
                    continue
                data[fname['name']] = self.x_decrypt_aes256(rec[fname['name']])
            rec.write(data)

    # === PRIVATE METHODS === #
    @ormcache('self.env.uid', 'self.env.su')
    def _x_get_encrypt_fields(self):
        model_fields = [
            {
                'name': name,
                'limit': getattr(field, 'encrypt_search_limit', None)
            }
            for name, field in self._fields.items()
            if getattr(field, 'encrypt', None)
        ]
        return model_fields

    def _x_get_normalized_text(self, plaintext):
        if not plaintext:
            return plaintext
        plaintext = plaintext.lower()
        plaintext = unicodedata.normalize('NFD', plaintext)
        return ''.join(char for char in plaintext if unicodedata.category(char) != 'Mn')

    # === SEARCH HELPERS === #
    @ormcache('field_name')
    def _x_get_search_helper_field_name(self, field_name):
        return 'x_' + field_name + '_search_ids'

    def _x_get_search_helper_data(self, fname, value):
        codes = self._x_get_encryption_search_codes()

        if not value:
            return value

        value = self._x_get_normalized_text(value)

        limit = fname.get('limit')
        if limit:
            value = value[limit[0]:limit[1]]

        value_split = value.split()

        def get_random_code():
            code = None
            while code is None:
                aux = ''.join(random.choices(string.ascii_uppercase, k=3))
                if aux not in codes:
                    code = aux
            return code

        records = []

        acc = []
        for i, part in enumerate(value_split):
            acc.append(part)
            if i == 0:
                records.append({
                    'field_name': fname['name'],
                    'code': get_random_code(),
                    'name': self.x_encrypt_aes256_helper(' '.join(acc)),
                })
                continue
            # Individual parts
            if len(part) >= 3:
                records.append({
                    'field_name': fname['name'],
                    'code': get_random_code(),
                    'name': self.x_encrypt_aes256_helper(part),
                })
            # Accumulated
            records.append({
                'field_name': fname['name'],
                'code': codes[i],
                'name': self.x_encrypt_aes256_helper(' '.join(acc)),
            })

        if random.randint(1, 100) <= 10:
            records.append({
                'field_name': fname['name'],
                'code': codes[-(random.randint(1, 5))],
                'name': self.x_encrypt_aes256_helper(''.join(random.choices(string.ascii_lowercase, k=2))),
            })
        random.shuffle(records)

        result = self._x_process_search_helper_data(fname, records)

        return result

    def _x_process_search_helper_data(self, fname, records):
        field_name = self._x_get_search_helper_field_name(fname['name'])
        field = self._fields[field_name]
        comodel_name = (field.comodel_name or '')[:-4]
        result = []
        for record in records:
            value = record['name']
            code = record['code']
            exist = self.env[comodel_name].search([('name', '=', value)])
            if not exist:
                exist = self.env[comodel_name].create({
                    'code': code,
                    'name': value,
                })
            result.append(Command.create({
                'encrypt_helper_id': exist.id,
                'field_name': record['field_name'],
            }))

        return result

    # === ENCRYPTION === #
    def x_encrypt_aes256(self, plaintext):
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
            key = self._x_get_encryption_key()

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

        except Exception:
            return plaintext

    def x_decrypt_aes256(self, encrypted_text):
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
            key = self._x_get_encryption_key()

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

        except Exception:
            return encrypted_text

    def x_encrypt_aes256_helper(self, plaintext):
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
            key = self._x_get_encryption_search_key()

            # Generate a random 16-byte IV
            encryption_iv = SHA256.new(plaintext.encode()).digest()[:16]

            # Create the cipher object
            cipher = AES.new(key, AES.MODE_CBC, encryption_iv)

            # Apply padding to the text
            padded_text = pad(plaintext.encode('utf-8'), AES.block_size)

            # Encrypt
            encrypted = cipher.encrypt(padded_text)

            # Combine IV + encrypted data and encode in base64
            result = base64.b64encode(encryption_iv + encrypted).decode('utf-8')

            return result

        except Exception:
            return plaintext

    def x_decrypt_aes256_helper(self, encrypted_text):
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
            key = self._x_get_encryption_search_key()

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

        except Exception:
            return encrypted_text

    @ormcache()
    def _x_get_encryption_key(self):
        """
        Generates a 32-byte key from the defined constant
        """
        encryption_key = config.get('x_encryption_key', 'MySecretKey')
        return hashlib.sha256(encryption_key.encode('utf-8')).digest()

    @ormcache()
    def _x_get_encryption_search_key(self):
        """
        Generates a 32-byte key from the defined constant
        """
        encryption_key = config.get('x_encryption_search_key', 'MySecretSearchKey')
        return hashlib.sha256(encryption_key.encode('utf-8')).digest()

    @ormcache()
    def _x_get_encryption_search_codes(self) -> list[str]:
        codes = config.get('x_encryption_search_codes')
        if not isinstance(codes, list):
            codes = eval(codes)
        return codes


class CustomModelEncryptionSearchHelperRel(models.AbstractModel):
    _name = 'custom.model.encryption.search.helper.rel'
    _description = 'Model Encryption Search Helper Rel'

    encrypt_model_id = fields.Many2one(
        'custom.model.encryption',
        ondelete='cascade', index=True, required=True)
    encrypt_helper_id = fields.Many2one(
        'custom.model.encryption.search.helper',
        ondelete='cascade', index=True, required=True)
    field_name = fields.Char(default='name', index=True, required=True)


class CustomModelEncryptionSearchHelper(models.AbstractModel):
    _name = 'custom.model.encryption.search.helper'
    _description = 'Model Encryption Search Helper'

    code = fields.Char(index='trigram', size=3, required=True)
    name = fields.Char()

    encrypt_rel_ids = fields.One2many('custom.model.encryption.search.helper.rel', 'encrypt_helper_id')
