from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from typing import Any

from doc_agent.config import get_settings
from doc_agent.users.models import UserConfig, utc_now


TOKEN_MASK = "***HIDDEN***"


class UserManager:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else get_settings().data_dir / "users"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.current_user: UserConfig | None = self.get_current_user()

    def create_user(self, user_config: UserConfig) -> UserConfig:
        user_file = self._user_path(user_config.user_id)
        if user_file.exists():
            raise ValueError(f"User {user_config.user_id} already exists")
        self._save_user(user_config)
        return self._masked(user_config)

    def get_user(self, user_id: str, include_secret: bool = False) -> UserConfig | None:
        user_file = self._user_path(user_id)
        if not user_file.exists():
            return None
        user = UserConfig.model_validate(json.loads(user_file.read_text(encoding="utf-8")))
        if include_secret:
            user.auth_token = self._decrypt_token(user.auth_token)
            return user
        return self._masked(user)

    def get_current_user(self, include_secret: bool = False) -> UserConfig | None:
        current_file = self.storage_path / ".current_user"
        if not current_file.exists():
            return None
        user_id = current_file.read_text(encoding="utf-8").strip()
        if not user_id:
            return None
        return self.get_user(user_id, include_secret=include_secret)

    def update_user(self, user_id: str, updates: dict[str, Any]) -> UserConfig:
        user = self.get_user(user_id, include_secret=True)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        clean_updates = {key: value for key, value in updates.items() if value is not None}
        for key, value in clean_updates.items():
            if key == "auth_token" and value == TOKEN_MASK:
                continue
            if hasattr(user, key):
                setattr(user, key, value)
        user.last_used = utc_now()
        self._save_user(user)
        return self._masked(user)

    def delete_user(self, user_id: str) -> bool:
        user_file = self._user_path(user_id)
        if not user_file.exists():
            return False
        user_file.unlink()
        current_file = self.storage_path / ".current_user"
        if current_file.exists() and current_file.read_text(encoding="utf-8").strip() == user_id:
            current_file.unlink()
        return True

    def list_users(self) -> list[UserConfig]:
        users: list[UserConfig] = []
        for user_file in sorted(self.storage_path.glob("*.json")):
            users.append(UserConfig.model_validate(json.loads(user_file.read_text(encoding="utf-8"))))
        return [self._masked(user) for user in users]

    def switch_user(self, user_id: str) -> UserConfig:
        user = self.get_user(user_id, include_secret=True)
        if user is None:
            raise ValueError(f"User {user_id} not found")
        user.last_used = utc_now()
        self._save_user(user)
        (self.storage_path / ".current_user").write_text(user_id, encoding="utf-8")
        self.current_user = self._masked(user)
        return self.current_user

    def _user_path(self, user_id: str) -> Path:
        safe_id = Path(user_id).name
        return self.storage_path / f"{safe_id}.json"

    def _save_user(self, user: UserConfig) -> None:
        user_to_save = user.model_copy()
        user_to_save.auth_token = self._encrypt_token(self._decrypt_token(user.auth_token))
        self._user_path(user.user_id).write_text(user_to_save.model_dump_json(indent=2), encoding="utf-8")

    def _masked(self, user: UserConfig) -> UserConfig:
        return user.model_copy(update={"auth_token": TOKEN_MASK if user.auth_token else ""})

    def _encrypt_token(self, token: str) -> str:
        if not token or token == TOKEN_MASK:
            return ""
        if token.startswith("enc:v1:"):
            return token
        key = self._get_encryption_key()
        nonce = os.urandom(16)
        data = token.encode("utf-8")
        cipher = self._xor(data, self._keystream(key, nonce, len(data)))
        digest = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        return "enc:v1:" + ":".join(
            base64.urlsafe_b64encode(part).decode("ascii") for part in (nonce, cipher, digest)
        )

    def _decrypt_token(self, encrypted_token: str) -> str:
        if not encrypted_token or encrypted_token == TOKEN_MASK:
            return ""
        if not encrypted_token.startswith("enc:v1:"):
            return encrypted_token
        try:
            _, _, nonce_raw, cipher_raw, digest_raw = encrypted_token.split(":", 4)
            nonce = base64.urlsafe_b64decode(nonce_raw.encode("ascii"))
            cipher = base64.urlsafe_b64decode(cipher_raw.encode("ascii"))
            digest = base64.urlsafe_b64decode(digest_raw.encode("ascii"))
        except Exception as exc:
            raise ValueError("Stored user token is malformed") from exc
        key = self._get_encryption_key()
        expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, digest):
            raise ValueError("Stored user token failed integrity check")
        return self._xor(cipher, self._keystream(key, nonce, len(cipher))).decode("utf-8")

    def _get_encryption_key(self) -> bytes:
        key_file = self.storage_path / ".encryption_key"
        if key_file.exists():
            return base64.urlsafe_b64decode(key_file.read_text(encoding="ascii").encode("ascii"))
        key = os.urandom(32)
        key_file.write_text(base64.urlsafe_b64encode(key).decode("ascii"), encoding="ascii")
        try:
            key_file.chmod(0o600)
        except OSError:
            pass
        return key

    @staticmethod
    def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
        output = bytearray()
        counter = 0
        while len(output) < length:
            output.extend(hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest())
            counter += 1
        return bytes(output[:length])

    @staticmethod
    def _xor(left: bytes, right: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(left, right))
