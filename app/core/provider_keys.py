"""Authenticated, row-bound encryption for provider API keys."""

import base64
import binascii
import json
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = "enc:v1:"


class ProviderConfigurationError(RuntimeError):
    """Safe to display; never includes key material or stored ciphertext."""


def encryption_key(value: str) -> bytes:
    try:
        raw = base64.b64decode(value, altchars=b"-_", validate=True)
        if len(raw) != 32:
            raise ValueError()
        return raw
    except (ValueError, binascii.Error):
        raise ProviderConfigurationError(
            "模型密钥加密配置缺失或无效，请联系管理员。"
        ) from None


def new_encryption_key() -> str:
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode("ascii")


def _aad(tenant_id: str, provider_id: str) -> bytes:
    return json.dumps(
        ["provider:v1", tenant_id, provider_id], separators=(",", ":")
    ).encode()


def encrypt_api_key(
    value: str, tenant_id: str, provider_id: str, master_key: str
) -> str:
    if not value:
        return ""
    if len(value.encode()) > 256 or any(
        ord(char) < 32 or ord(char) == 127 for char in value
    ):
        raise ProviderConfigurationError(
            "API Key 需为不含控制字符、长度不超过 256 字节的文本。"
        )
    nonce = os.urandom(12)
    ciphertext = AESGCM(encryption_key(master_key)).encrypt(
        nonce, value.encode(), _aad(tenant_id, provider_id)
    )
    return PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt_api_key(
    value: str, tenant_id: str, provider_id: str, master_key: str
) -> str:
    if not value:
        return ""
    if not value.startswith(PREFIX):
        raise ProviderConfigurationError(
            "旧格式模型密钥需要由管理员重新保存加密后使用。"
        )
    try:
        packed = base64.b64decode(value[len(PREFIX) :], altchars=b"-_", validate=True)
        return (
            AESGCM(encryption_key(master_key))
            .decrypt(packed[:12], packed[12:], _aad(tenant_id, provider_id))
            .decode()
        )
    except (ValueError, binascii.Error, InvalidTag, UnicodeDecodeError):
        raise ProviderConfigurationError(
            "模型密钥无法解密，请检查加密主密钥或重新保存凭据。"
        ) from None
