import logging,time
from datetime import datetime
from pathlib import Path
from redis import Redis
from sqlalchemy import select
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import AnalysisRun,FootfallSample,Stall
from src.services.analysis_engine import analyze_samples
from src.services.audit import record
from migrations.initial import migrate
logging.basicConfig(level=logging.INFO)
def execute(run_id):
    with Session() as db:
        run=db.get(AnalysisRun,run_id)
        if not run or run.status not in ('queued','running'):return
        run.status='running';db.commit()
        try:
            rows=list(db.scalars(select(FootfallSample).where(FootfallSample.id.in_(run.sample_ids))));codes={s.id:s.code for s in db.scalars(select(Stall).where(Stall.id.in_([r.stall_id for r in rows])))}
            payload=[{'stall_code':codes.get(r.stall_id,''),'sampled_at':r.sampled_at,'status':r.status,'issue_reason':r.issue_reason,'footfall':r.footfall,'transactions':r.transactions,'revenue':r.revenue,'dwell_seconds':r.dwell_seconds,'hour_index':r.sampled_at.hour+r.sampled_at.minute/60} for r in rows]
            result=analyze_samples(payload);run.result=result;run.status='completed' if result.get('explainable') else 'unexplainable';run.review_status='pending' if result.get('explainable') else 'blocked';run.completed_at=datetime.utcnow();record(db,'worker','analysis.completed',{'id':run.id,'status':run.status});db.commit()
        except Exception as exc:
            logging.exception('analysis failed');run.status='failed';run.review_status='blocked';run.result={'explainable':False,'reason':str(exc)};run.completed_at=datetime.utcnow();db.commit()
def main():
    migrate();client=Redis.from_url(REDIS_URL,socket_timeout=3)
    while True:
        Path('/tmp/heartbeat').touch()
        try:
            item=client.blpop('market-footfall:analysis',timeout=1)
            if item:execute(int(item[1]))
        except Exception:logging.exception('worker retry');time.sleep(2)
if __name__=='__main__':main()
