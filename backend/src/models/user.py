from sqlalchemy import String,Integer,DateTime,func
from sqlalchemy.orm import Mapped,mapped_column
from src.config.database import Base
class User(Base):
    __tablename__='users'; id:Mapped[int]=mapped_column(Integer,primary_key=True); email:Mapped[str]=mapped_column(String(160),unique=True,index=True); name:Mapped[str]=mapped_column(String(80)); role:Mapped[str]=mapped_column(String(20)); password_hash:Mapped[str]=mapped_column(String(255)); created_at:Mapped[object]=mapped_column(DateTime,server_default=func.now())
