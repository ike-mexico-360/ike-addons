# -*- coding: utf-8 -*-

from . import models


from random import choices
from string import ascii_uppercase
from odoo.tools import config


def _custom_encrypt_post_init(env):
    if not config.get('x_encryption_key'):
        config.options['x_encryption_key'] = 'MyEncryptionSecretKey'
        config.save('x_encryption_key')
    if not config.get('x_encryption_search_key'):
        config.options['x_encryption_search_key'] = 'MyEncryptionSearchSecretKey'
        config.save('x_encryption_search_key')

    if not config.get('x_encryption_search_codes'):
        codes = []

        def get_random_code():
            code = None
            while code is None:
                aux = ''.join(choices(ascii_uppercase, k=3))
                if aux not in codes:
                    code = aux
            return code

        for i in range(12):
            codes.append(get_random_code())

        config.options['x_encryption_search_codes'] = codes
        config.save('x_encryption_search_codes')
