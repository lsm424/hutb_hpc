'''
Author: wadesmli
Date: 2026-05-29 16:32:34
LastEditors: wadesmli
LastEditTime: 2026-06-01 09:12:36
FilePath: auth.py
Description: 

Copyright (c) 2026 by wadesmli, All Rights Reserved. 
'''
"""
Author: wadesmli
Date: 2026-05-29
Description: Authentication utilities for HPC Dashboard
"""
from datetime import datetime, timedelta
import jwt
from fastapi import Request, HTTPException
from common import cfg

# JWT配置
SECRET_KEY = cfg.get('auth', 'secret_key', fallback='hpc-dashboard-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8

# 硬编码账号密码（生产环境应使用数据库存储+密码哈希）
USERS = {
    "admin": {
        "password": "admin@123",
        "role": "admin",
        "name": "管理员"
    }
}


def create_access_token(data: dict, expires_delta: timedelta = None):
    """创建JWT访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str):
    """验证JWT令牌"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if username is None:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.JWTError:
        return None


def get_current_user(request: Request):
    """获取当前登录用户"""
    token = request.cookies.get("access_token")
    if not token:
        return None
    
    payload = verify_token(token)
    if not payload:
        return None
    
    return payload


def check_auth(request: Request):
    """检查是否已认证"""
    user = get_current_user(request)
    return user is not None


# FastAPI中间件工厂函数
def create_auth_middleware(app):
    """创建认证中间件"""
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import RedirectResponse
    
    class AuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # 不需要认证的路径
            public_paths = ['/login', '/assets', '/_dash', '/favicon.ico']
            
            path = request.url.path
            
            # 检查是否是公开路径
            is_public = any(path.startswith(p) for p in public_paths)
            
            if not is_public:
                # 检查认证状态
                user = get_current_user(request)
                if not user:
                    # 未登录，重定向到登录页
                    if request.method == "GET":
                        return RedirectResponse(url="/login", status_code=302)
            
            response = await call_next(request)
            return response
    
    return AuthMiddleware
