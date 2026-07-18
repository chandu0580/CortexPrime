"""
Multi-tenant authentication and organization isolation.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Tenant:
    tenant_id: str
    name: str
    slug: str
    domain: Optional[str] = None
    plan: str = "free"
    is_active: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TenantUser:
    user_id: str
    tenant_id: str
    email: str
    role: str = "member"  # member, admin, owner
    is_active: bool = True
    permissions: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TenantManager:
    """Manages tenants and tenant-user associations with file persistence."""

    def __init__(self, storage_path: str = "data/tenants"):
        from pathlib import Path
        self._tenants: Dict[str, Tenant] = {}
        self._tenant_users: Dict[str, List[TenantUser]] = {}
        self._storage_path = Path(storage_path)
        self._storage_path.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        import json
        tenants_file = self._storage_path / "tenants.json"
        users_file = self._storage_path / "tenant_users.json"
        if tenants_file.exists():
            data = json.loads(tenants_file.read_text())
            for t in data:
                self._tenants[t["tenant_id"]] = Tenant(**t)
        if users_file.exists():
            data = json.loads(users_file.read_text())
            for tenant_id, users in data.items():
                self._tenant_users[tenant_id] = [TenantUser(**u) for u in users]

    def _save(self):
        import json
        tenants_data = [vars(t) for t in self._tenants.values()]
        (self._storage_path / "tenants.json").write_text(json.dumps(tenants_data, indent=2, default=str))
        users_data = {tid: [vars(u) for u in users] for tid, users in self._tenant_users.items()}
        (self._storage_path / "tenant_users.json").write_text(json.dumps(users_data, indent=2, default=str))

    def create_tenant(self, name: str, slug: str, domain: Optional[str] = None, plan: str = "free") -> Tenant:
        tenant = Tenant(
            tenant_id=f"tenant-{uuid.uuid4().hex[:12]}",
            name=name, slug=slug, domain=domain, plan=plan,
        )
        self._tenants[tenant.tenant_id] = tenant
        self._tenant_users[tenant.tenant_id] = []
        self._save()
        return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)

    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        for t in self._tenants.values():
            if t.slug == slug:
                return t
        return None

    def list_tenants(self) -> List[Tenant]:
        return list(self._tenants.values())

    def add_user(self, tenant_id: str, email: str, role: str = "member") -> Optional[TenantUser]:
        if tenant_id not in self._tenants:
            return None
        user = TenantUser(
            user_id=f"user-{uuid.uuid4().hex[:12]}",
            tenant_id=tenant_id, email=email, role=role,
        )
        self._tenant_users.setdefault(tenant_id, []).append(user)
        self._save()
        return user

    def get_users(self, tenant_id: str) -> List[TenantUser]:
        return self._tenant_users.get(tenant_id, [])

    def get_user_by_email(self, email: str) -> Optional[TenantUser]:
        for users in self._tenant_users.values():
            for u in users:
                if u.email == email:
                    return u
        return None

    def update_user_role(self, tenant_id: str, user_id: str, role: str) -> bool:
        for u in self._tenant_users.get(tenant_id, []):
            if u.user_id == user_id:
                u.role = role
                self._save()
                return True
        return False

    def deactivate_tenant(self, tenant_id: str) -> bool:
        if tenant_id in self._tenants:
            self._tenants[tenant_id].is_active = False
            self._save()
            return True
        return False


# Singleton
_tenant_manager: Optional[TenantManager] = None


def get_tenant_manager() -> TenantManager:
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager
