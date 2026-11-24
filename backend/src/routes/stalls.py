from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models import Stall
from src.schemas.market import StallIn
from src.middlewares.auth import current_user,require_roles
from src.services.audit import record
from src.utils.serialization import stall_dict
router=APIRouter(prefix='/stalls')
@router.get('')
def list_stalls(db:Session=Depends(get_db),u=Depends(current_user)): return [stall_dict(s) for s in db.scalars(select(Stall).order_by(Stall.code))]
@router.post('',status_code=201)
def create_stall(p:StallIn,db:Session=Depends(get_db),u=Depends(require_roles('admin'))):
    if db.scalar(select(Stall).where(Stall.code==p.code)): raise HTTPException(409,'摊位编码已存在')
    s=Stall(**p.model_dump());db.add(s);record(db,u.email,'stall.created',{'code':p.code});db.commit();db.refresh(s);return stall_dict(s)
