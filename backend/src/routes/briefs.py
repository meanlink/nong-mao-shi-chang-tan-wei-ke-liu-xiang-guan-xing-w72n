from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models import Brief,AnalysisRun
from src.schemas.market import BriefIn
from src.middlewares.auth import current_user,require_roles
from src.services.audit import record
from src.utils.serialization import brief_dict
router=APIRouter(prefix='/briefs')
@router.get('')
def list_briefs(db:Session=Depends(get_db),u=Depends(current_user)):return [brief_dict(b) for b in db.scalars(select(Brief).order_by(Brief.id.desc()))]
@router.post('',status_code=201)
def create_brief(p:BriefIn,db:Session=Depends(get_db),u=Depends(require_roles('admin','analyst'))):
    a=db.get(AnalysisRun,p.analysis_id)
    if not a or a.status!='completed' or a.review_status!='approved' or not a.result or not a.result.get('explainable'):raise HTTPException(409,'只有通过解释性检查并完成运营复核的分析才能生成招商简报')
    if db.scalar(select(Brief).where(Brief.analysis_id==a.id)):raise HTTPException(409,'该分析已经生成过招商简报')
    rows=a.result.get('stall_findings',[]);summary=f"{a.result.get('headline')}。建议优先关注 {', '.join(x['stall_code'] for x in rows if x['signal']=='优先招商') or '客流稳定但需补采样的摊位'}。"
    b=Brief(analysis_id=a.id,title=p.title,status='draft',summary=summary,recommended_stalls=rows,audience=p.audience);db.add(b);db.flush();record(db,u.email,'brief.created',{'id':b.id,'analysis_id':a.id});db.commit();db.refresh(b);return brief_dict(b)
@router.post('/{brief_id}/issue')
def issue(brief_id:int,db:Session=Depends(get_db),u=Depends(require_roles('admin'))):
    b=db.get(Brief,brief_id)
    if not b:raise HTTPException(404,'招商简报不存在')
    b.status='issued';b.issued_by=u.id;b.issued_at=datetime.utcnow();record(db,u.email,'brief.issued',{'id':b.id});db.commit();return brief_dict(b)
