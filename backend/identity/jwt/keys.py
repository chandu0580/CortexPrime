from __future__ import annotations

from backend.infrastructure.redis.keys import RedisKeys


class IdentityRedisKeys:
    ACCESS_BLACKLIST = "cx:identity:bl:access"
    REFRESH_BLACKLIST = "cx:identity:bl:refresh"
    USER_REVOKE_PREFIX = "cx:identity:bl:user:"
    SESSION_PREFIX = "cx:identity:sess:"
    KEY_STORE_PREFIX = "cx:identity:keys:"

    @staticmethod
    def jti_key(jti: str) -> str:
        return f"{IdentityRedisKeys.ACCESS_BLACKLIST}:{jti}"

    @staticmethod
    def refresh_jti_key(jti: str) -> str:
        return f"{IdentityRedisKeys.REFRESH_BLACKLIST}:{jti}"

    @staticmethod
    def user_revoke_key(user_id: str) -> str:
        return f"{IdentityRedisKeys.USER_REVOKE_PREFIX}{user_id}"

    @staticmethod
    def session_key(user_id: str) -> str:
        return f"{IdentityRedisKeys.SESSION_PREFIX}{user_id}"

    @staticmethod
    def keystore_key(kid: str) -> str:
        return f"{IdentityRedisKeys.KEY_STORE_PREFIX}{kid}"
