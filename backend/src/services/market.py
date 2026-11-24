from src.models import CampaignWindow,Stall
def classify_sample(db,sample):
    if sample.footfall<5 or sample.transactions<0 or sample.revenue<0:
        sample.status='insufficient'; sample.issue_reason='客流或交易值不足以形成可解释时段'; return sample
    if sample.campaign_window_id:
        campaign=db.get(CampaignWindow,sample.campaign_window_id)
        if not campaign or (sample.campaign_label and sample.campaign_label!=campaign.label): sample.status='conflicting'; sample.issue_reason='促销标签与活动窗口口径冲突'; return sample
        if sample.sampled_at<campaign.starts_at or sample.sampled_at>campaign.ends_at: sample.status='conflicting'; sample.issue_reason='采样时间不在活动窗口内'; return sample
    sample.status='valid';sample.issue_reason='';return sample
def sample_dict(db,s):
    stall=db.get(Stall,s.stall_id); campaign=db.get(CampaignWindow,s.campaign_window_id) if s.campaign_window_id else None
    return {'id':s.id,'stall_id':s.stall_id,'stall_code':stall.code if stall else '','stall_name':stall.name if stall else '','campaign_window_id':s.campaign_window_id,'campaign_name':campaign.name if campaign else '无活动','sampled_at':s.sampled_at.isoformat(),'window_label':s.window_label,'footfall':s.footfall,'transactions':s.transactions,'revenue':s.revenue,'dwell_seconds':s.dwell_seconds,'weather':s.weather,'campaign_label':s.campaign_label,'status':s.status,'issue_reason':s.issue_reason,'source':s.source,'notes':s.notes}
