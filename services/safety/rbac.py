"""Role-Based Access Control (RBAC) and security boundary enforcement."""
from enum import Enum
from typing import Set, Dict, Any, Optional
from pydantic import BaseModel


class UserRole(str, Enum):
    VIEWER = "VIEWER"        # Read-only telemetry, incidents, and past investigations
    ENGINEER = "ENGINEER"    # Can run live investigations and validation checks
    APPROVER = "APPROVER"    # Can approve simulated action requests (e.g. simulated breaker reclose)


class Permission(str, Enum):
    VIEW_INCIDENTS = "VIEW_INCIDENTS"
    VIEW_TELEMETRY = "VIEW_TELEMETRY"
    RUN_INVESTIGATION = "RUN_INVESTIGATION"
    RUN_VALIDATION = "RUN_VALIDATION"
    SUBMIT_SIMULATED_ACTION = "SUBMIT_SIMULATED_ACTION"
    APPROVE_SIMULATED_ACTION = "APPROVE_SIMULATED_ACTION"


ROLE_PERMISSIONS: Dict[UserRole, Set[Permission]] = {
    UserRole.VIEWER: {
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_TELEMETRY,
    },
    UserRole.ENGINEER: {
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_TELEMETRY,
        Permission.RUN_INVESTIGATION,
        Permission.RUN_VALIDATION,
        Permission.SUBMIT_SIMULATED_ACTION,
    },
    UserRole.APPROVER: {
        Permission.VIEW_INCIDENTS,
        Permission.VIEW_TELEMETRY,
        Permission.RUN_INVESTIGATION,
        Permission.RUN_VALIDATION,
        Permission.SUBMIT_SIMULATED_ACTION,
        Permission.APPROVE_SIMULATED_ACTION,
    },
}


class SecurityContext(BaseModel):
    user_id: str
    username: str
    role: UserRole

    def has_permission(self, permission: Permission) -> bool:
        allowed = ROLE_PERMISSIONS.get(self.role, set())
        return permission in allowed

    def require_permission(self, permission: Permission):
        if not self.has_permission(permission):
            raise PermissionError(f"User '{self.username}' with role '{self.role.value}' lacks required permission: '{permission.value}'")
