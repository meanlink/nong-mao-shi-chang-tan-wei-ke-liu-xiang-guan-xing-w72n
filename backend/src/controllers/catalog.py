from fastapi import APIRouter,Depends
from sqlalchemy import select,func
from sqlalchemy.orm import Session
from src.config.database import get_db
from src.models import Stall,FootfallSample,CampaignWindow,AnalysisRun,Brief,AuditLog
from src.middlewares.auth import current_user
from src.services.attribution import is_current_sample
router=APIRouter()
@router.get('/meta')
def meta():return {'name':'农贸市场摊位客流相关性','short':'market-footfall-correlation','tagline':'把摊位客流、活动标签与招商判断放在同一张运营台上','client':'澄湾农贸市场运营组，36 个固定摊位，招商委员会每周一复盘','workflow':['纸笔记录时段客流','活动群补促销标签','运营专员合并成交与停留时长','分析师复核相关性','招商经理发送简报'],'pains':['采样时段不齐，无法横向比较','促销标签来自多个群聊，常出现口径冲突','招商简报缺少滞后效应与可追溯复核'],'upstream':'收银台交易汇总、入口计数器、活动排期表与摊主反馈','downstream':'招商委员会、空铺招商专员、市场活动排期负责人','entities':['摊位档案 Stall','客流样本 FootfallSample','活动窗口 CampaignWindow','分析运行 AnalysisRun','招商简报 Brief'],'roles':[{'role':'admin','label':'市场管理员','actions':'维护摊位与活动窗口、发出招商简报、查看审计'},{'role':'analyst','label':'运营分析师','actions':'录入样本、运行分析、提交复核、创建简报草稿'},{'role':'viewer','label':'招商观察员','actions':'查看样本、分析结果与已发简报'}],'enums':{'sample_status':['valid','insufficient','conflicting','excluded'],'analysis_status':['queued','running','completed','unexplainable','failed'],'review_status':['pending','approved','rejected','blocked']},'method':'Spearman 偏相关控制停留时长与小时序号，滞后矩阵覆盖 -2 至 +2 时段'}
@router.get('/overview')
def overview(db:Session=Depends(get_db),u=Depends(current_user)):
    total=db.scalar(select(func.count()).select_from(FootfallSample).where(is_current_sample())) or 0;valid=db.scalar(select(func.count()).select_from(FootfallSample).where(FootfallSample.status=='valid',is_current_sample())) or 0
    return {'stalls':db.scalar(select(func.count()).select_from(Stall)) or 0,'samples':total,'valid_samples':valid,'blocked_samples':total-valid,'campaigns':db.scalar(select(func.count()).select_from(CampaignWindow)) or 0,'analyses':db.scalar(select(func.count()).select_from(AnalysisRun)) or 0,'approved_analyses':db.scalar(select(func.count()).select_from(AnalysisRun).where(AnalysisRun.review_status=='approved')) or 0,'briefs':db.scalar(select(func.count()).select_from(Brief)) or 0,'latest':[{'label':a.name,'status':a.status,'at':a.created_at.isoformat() if a.created_at else ''} for a in db.scalars(select(AnalysisRun).order_by(AnalysisRun.id.desc()).limit(4))]}
@router.get('/audits')
def audits(db:Session=Depends(get_db),u=Depends(current_user)):return [{'actor':x.actor,'action':x.action,'detail':x.detail,'created_at':x.created_at.isoformat() if x.created_at else ''} for x in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(30))]
