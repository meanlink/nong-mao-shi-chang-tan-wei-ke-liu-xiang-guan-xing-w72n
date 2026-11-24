from datetime import datetime,timedelta,date
from sqlalchemy import select
from src.config.database import Session
from src.models import User,Stall,CampaignWindow,FootfallSample,ResamplingQuota,ResamplingClaim,ResamplingQuotaSlot
from src.utils.security import hash_password
from src.services.market import classify_sample
from migrations.initial import migrate
USERS=[('admin@demo.local','林霁','admin'),('analyst@demo.local','周析','analyst'),('viewer@demo.local','顾言','viewer')]
STALLS=[('A-07','青禾蔬果','蔬果','东棚','许岚',42,.92),('B-12','江南水产','水产','西棚','沈岸',78,.86),('C-03','禾下熟食','熟食','南门','叶笙',31,.74)]
def seed():
    migrate()
    with Session() as db:
        for email,name,role in USERS:
            if not db.scalar(select(User).where(User.email==email)):db.add(User(email=email,name=name,role=role,password_hash=hash_password('Demo123!')))
        db.flush();stalls={}
        for code,name,cat,zone,owner,ticket,occ in STALLS:
            s=db.scalar(select(Stall).where(Stall.code==code))
            if not s:s=Stall(code=code,name=name,category=cat,zone=zone,owner_name=owner,avg_ticket=ticket,occupancy_rate=occ);db.add(s);db.flush()
            stalls[code]=s
        base=datetime(2026,11,2,8);campaigns={}
        for code,name,label,start,end,zone in [('CAMP-MORN','早市满减','早市满减',base+timedelta(days=1),base+timedelta(days=1,hours=3),'东棚'),('CAMP-WEEK','周末鲜享','周末鲜享',base+timedelta(days=5,hours=8),base+timedelta(days=6,hours=12),'全场')]:
            c=db.scalar(select(CampaignWindow).where(CampaignWindow.code==code))
            if not c:c=CampaignWindow(code=code,name=name,label=label,starts_at=start,ends_at=end,target_zone=zone,status='active',owner='活动组',notes='从活动排期表同步');db.add(c);db.flush()
            campaigns[code]=c
        if not db.scalar(select(FootfallSample.id).limit(1)):
            windows=[('早市',8),('午市',11),('下午',15),('晚市',18)]
            for day in range(8):
                for code,stall in stalls.items():
                    for idx,(label,hour) in enumerate(windows):
                        stamp=base+timedelta(days=day,hours=hour-8);flow={'A-07':74,'B-12':62,'C-03':49}[code]+(day%3)*7+idx*9+(8 if day in (1,5) else 0);tx=max(5,round(flow*{'A-07':.19,'B-12':.16,'C-03':.13}[code]+(2 if idx==1 else 0)));c=campaigns['CAMP-MORN'] if day==1 and hour==8 and code=='A-07' else (campaigns['CAMP-WEEK'] if day in (5,6) and hour>=15 else None)
                        row=FootfallSample(stall_id=stall.id,campaign_window_id=c.id if c else None,sampled_at=stamp,window_label=label,footfall=flow,transactions=tx,revenue=tx*stall.avg_ticket,dwell_seconds=42+idx*9+(day%2)*3,weather='晴' if day not in (3,6) else '小雨',campaign_label=c.label if c else '',source='counter-card',notes='入口计数器与收银台双录');classify_sample(db,row);db.add(row)
            conflict=FootfallSample(stall_id=stalls['B-12'].id,campaign_window_id=campaigns['CAMP-MORN'].id,sampled_at=base+timedelta(days=1,hours=1),window_label='冲突样本',footfall=88,transactions=11,revenue=858,dwell_seconds=61,weather='晴',campaign_label='买一送一',source='activity-chat',notes='活动群标签与排期表不一致');classify_sample(db,conflict);db.add(conflict)
            short=FootfallSample(stall_id=stalls['C-03'].id,sampled_at=base+timedelta(days=9),window_label='不足样本',footfall=2,transactions=0,revenue=0,dwell_seconds=12,weather='晴',source='manual-note',notes='只有一次巡场记录');classify_sample(db,short);db.add(short)
        db.flush()
        admin_user=db.scalar(select(User).where(User.email=='admin@demo.local'))
        analyst_user=db.scalar(select(User).where(User.email=='analyst@demo.local'))
        today=date.today()
        if not db.scalar(select(ResamplingQuota).where(ResamplingQuota.quota_date==today)):
            db.add(ResamplingQuota(quota_date=today,total=5,created_by=admin_user.id));db.flush()
            db.add_all([ResamplingQuotaSlot(quota_date=today,slot_no=no,claim_id=None) for no in range(1,6)]);db.flush()
        if not db.scalar(select(ResamplingClaim).where(ResamplingClaim.claim_date==today)):
            # One pending order the patrol team can reconcile on the sampling page.
            pending=ResamplingClaim(stall_id=stalls['A-07'].id,claim_date=today,window_label='早市',status='pending',note='早市巡场漏记，需补采',claimed_by=analyst_user.id,claimed_by_name=analyst_user.name);db.add(pending);db.flush()
            # One fulfilled order demonstrating quota occupation and reconciliation.
            good=FootfallSample(stall_id=stalls['B-12'].id,sampled_at=datetime.combine(today,datetime.min.time()).replace(hour=8),window_label='早市',footfall=57,transactions=9,revenue=702,dwell_seconds=48,weather='晴',source='manual-note',notes='补采有效样本');classify_sample(db,good);db.add(good);db.flush()
            fulfilled=ResamplingClaim(stall_id=stalls['B-12'].id,claim_date=today,window_label='早市',status='fulfilled',note='摊位补采已核销',claimed_by=analyst_user.id,claimed_by_name=analyst_user.name,sample_id=good.id,fulfilled_at=datetime.now());db.add(fulfilled);db.flush();good.claim_id=fulfilled.id
            # The two live orders occupy two of the five shared seats; cancelled ones do not.
            for slot_no,cid in ((1,pending.id),(2,fulfilled.id)):
                db.query(ResamplingQuotaSlot).filter(ResamplingQuotaSlot.quota_date==today,ResamplingQuotaSlot.slot_no==slot_no).update({'claim_id':cid})
            db.flush()
            # A cancelled order: a late submission afterwards is archived, never reconciled.
            cancelled=ResamplingClaim(stall_id=stalls['C-03'].id,claim_date=today,window_label='午市',status='cancelled',note='人手调整，撤销认领',claimed_by=analyst_user.id,claimed_by_name=analyst_user.name,cancelled_at=datetime.now());db.add(cancelled);db.flush()
            late=FootfallSample(stall_id=stalls['C-03'].id,sampled_at=datetime.combine(today,datetime.min.time()).replace(hour=11),window_label='午市',footfall=33,transactions=6,revenue=186,dwell_seconds=35,weather='晴',source='manual-note',notes='撤销后迟到的补录，留档不核销 / 对应认领单已撤销，样本留档待补');classify_sample(db,late);db.add(late)
        db.commit();print({'users':len(USERS),'stalls':len(stalls),'samples':db.scalar(select(FootfallSample.id).order_by(FootfallSample.id.desc()))})
if __name__=='__main__':seed()
