from fastapi import Depends,HTTPException,Request
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models import User
from src.utils.security import decode_token
def current_user(request:Request,db:Session=Depends(get_db)):
    header=request.headers.get('Authorization','')
    if not header.startswith('Bearer '): raise HTTPException(401,'需要登录')
    try: user=db.get(User,decode_token(header[7:]))
    except Exception: user=None
    if not user: raise HTTPException(401,'登录已失效')
    return user
def require_roles(*roles):
    def dependency(user=Depends(current_user)):
        if user.role not in roles: raise HTTPException(403,'当前角色无权执行此操作')
        return user
    return dependency
