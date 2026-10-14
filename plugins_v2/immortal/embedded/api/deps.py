"""No standalone authentication; access only inside the platform admin bridge."""
from contextvars import ContextVar
from fastapi import HTTPException

bridge_authorized = ContextVar('immortal_admin_bridge', default=False)


def get_current_user():
    if not bridge_authorized.get():
        raise HTTPException(403, '请从平台管理员页面访问')
    from ..models.user import User
    return User(id=0, username='平台管理员')


def api_key_or_jwt():
    return get_current_user()
