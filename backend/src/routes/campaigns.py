from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models import CampaignWindow
from src.schemas.market import CampaignIn
from src.middlewares.auth import current_user,require_roles
from src.services.audit import record
from src.utils.serialization import campaign_dict
router=APIRouter(prefix='/campaigns')
@router.get('')
def list_campaigns(db:Session=Depends(get_db),u=Depends(current_user)): return [campaign_dict(c) for c in db.scalars(select(CampaignWindow).order_by(CampaignWindow.starts_at.desc()))]
@router.post('',status_code=201)
def create_campaign(p:CampaignIn,db:Session=Depends(get_db),u=Depends(require_roles('admin','analyst'))):
    if p.ends_at<=p.starts_at:raise HTTPException(422,'活动结束时间必须晚于开始时间')
    if db.scalar(select(CampaignWindow).where(CampaignWindow.code==p.code)):raise HTTPException(409,'活动编码已存在')
    c=CampaignWindow(**p.model_dump());db.add(c);record(db,u.email,'campaign.created',{'code':p.code});db.commit();db.refresh(c);return campaign_dict(c)
