from datetime import datetime
from pydantic import BaseModel,Field
class LoginIn(BaseModel): email:str; password:str
class StallIn(BaseModel): code:str=Field(min_length=2); name:str=Field(min_length=2); category:str; zone:str; owner_name:str; avg_ticket:float=0; occupancy_rate:float=0
class CampaignIn(BaseModel): code:str; name:str; label:str; starts_at:datetime; ends_at:datetime; target_zone:str; owner:str; notes:str=''
class SampleIn(BaseModel): stall_id:int; campaign_window_id:int|None=None; sampled_at:datetime; window_label:str; footfall:int=Field(ge=0); transactions:int=Field(ge=0); revenue:float=Field(ge=0); dwell_seconds:float=Field(ge=0); weather:str='晴'; campaign_label:str=''; source:str='counter-card'; notes:str=''
class AnalysisIn(BaseModel): name:str=Field(min_length=3); sample_ids:list[int]|None=None
class ReviewIn(BaseModel): decision:str; note:str=''
class BriefIn(BaseModel): analysis_id:int; title:str=Field(min_length=3); audience:str='招商委员会'
