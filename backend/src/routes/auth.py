from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models import User
from src.schemas.market import LoginIn
from src.middlewares.auth import current_user
from src.utils.security import verify_password,token_for
router=APIRouter(prefix='/auth')
@router.post('/login')
def login(p:LoginIn,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==p.email))
    if not u or not verify_password(p.password,u.password_hash): raise HTTPException(401,'邮箱或密码错误')
    return {'access_token':token_for(u),'user':{'id':u.id,'email':u.email,'name':u.name,'role':u.role}}
@router.get('/me')
def me(u=Depends(current_user)): return {'id':u.id,'email':u.email,'name':u.name,'role':u.role}
