from datetime import datetime
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from redis import Redis
from src.config.database import get_db
from src.config.settings import REDIS_URL
from src.models import AnalysisRun,FootfallSample
from src.schemas.market import AnalysisIn,ReviewIn
from src.middlewares.auth import current_user,require_roles
from src.services.audit import record
from src.utils.serialization import analysis_dict
from src.services.attribution import is_current_sample
router=APIRouter(prefix='/analysis')
@router.get('')
def list_runs(db:Session=Depends(get_db),u=Depends(current_user)):return [analysis_dict(a) for a in db.scalars(select(AnalysisRun).order_by(AnalysisRun.id.desc()))]
@router.post('',status_code=202)
def create_run(p:AnalysisIn,db:Session=Depends(get_db),u=Depends(require_roles('admin','analyst'))):
    ids=sorted(set(p.sample_ids)) if p.sample_ids else [s.id for s in db.scalars(select(FootfallSample).where(FootfallSample.status=='valid',is_current_sample()).order_by(FootfallSample.sampled_at))]
    if not ids:raise HTTPException(422,'没有可分析的有效样本')
    run=AnalysisRun(name=p.name,requested_by=u.id,sample_ids=ids,sample_count=len(ids));db.add(run);db.flush();record(db,u.email,'analysis.queued',{'id':run.id,'sample_count':len(ids)});db.commit();Redis.from_url(REDIS_URL).rpush('market-footfall:analysis',str(run.id));return analysis_dict(run)
@router.get('/{run_id}')
def get_run(run_id:int,db:Session=Depends(get_db),u=Depends(current_user)):
    a=db.get(AnalysisRun,run_id)
    if not a:raise HTTPException(404,'分析运行不存在')
    return analysis_dict(a)
@router.post('/{run_id}/review')
def review(run_id:int,p:ReviewIn,db:Session=Depends(get_db),u=Depends(require_roles('admin','analyst'))):
    a=db.get(AnalysisRun,run_id)
    if not a:raise HTTPException(404,'分析运行不存在')
    if a.status!='completed' or not a.result or not a.result.get('explainable'):raise HTTPException(409,'不可解释的分析不能进入运营复核或招商简报')
    if p.decision not in ('approve','reject'):raise HTTPException(422,'decision 只能是 approve 或 reject')
    a.review_status='approved' if p.decision=='approve' else 'rejected';a.review_note=p.note;record(db,u.email,'analysis.reviewed',{'id':a.id,'decision':p.decision});db.commit();return analysis_dict(a)
