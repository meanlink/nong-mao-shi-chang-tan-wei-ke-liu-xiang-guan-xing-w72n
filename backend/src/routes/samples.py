from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models import FootfallSample,Stall
from src.schemas.market import SampleIn
from src.middlewares.auth import current_user,require_roles
from src.services.audit import record
from src.services.market import classify_sample,sample_dict
from src.services.attribution import is_current_sample
router=APIRouter(prefix='/samples')
@router.get('')
def list_samples(status:str|None=None,db:Session=Depends(get_db),u=Depends(current_user)):
    q=select(FootfallSample).where(is_current_sample()).order_by(FootfallSample.sampled_at.desc(),FootfallSample.id.desc())
    if status:q=q.where(FootfallSample.status==status)
    return [sample_dict(db,s) for s in db.scalars(q.limit(250))]
@router.post('',status_code=201)
def create_sample(p:SampleIn,db:Session=Depends(get_db),u=Depends(require_roles('admin','analyst'))):
    if not db.get(Stall,p.stall_id):raise HTTPException(404,'摊位不存在')
    data=p.model_dump(); data['sampled_at']=data['sampled_at'].replace(tzinfo=None); s=FootfallSample(**data);classify_sample(db,s);db.add(s);db.flush();record(db,u.email,'sample.created',{'id':s.id,'status':s.status,'issue_reason':s.issue_reason});db.commit();db.refresh(s);return sample_dict(db,s)
