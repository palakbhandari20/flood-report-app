from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True)
    user = Column(String)
    message = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    image_path = Column(String)   # Will store Supabase public URL in production
    severity = Column(String)