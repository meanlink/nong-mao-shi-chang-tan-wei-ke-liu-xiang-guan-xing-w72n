import logging,os
from contextlib import asynccontextmanager
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.middlewares.requests import RequestControl
from src.routes import auth,stalls,campaigns,samples,analysis,briefs,attribution
from src.controllers import catalog
from migrations.initial import migrate
@asynccontextmanager
async def lifespan(app):
    migrate()
    if os.getenv('SEED_DEMO','true').lower()=='true':
        try:
            from scripts.seed_demo import seed;seed()
        except Exception:logging.exception('seed failed')
    yield
app=FastAPI(title='农贸市场摊位客流相关性',lifespan=lifespan);app.add_middleware(RequestControl)
@app.exception_handler(Exception)
async def unhandled(request:Request,exc:Exception):logging.exception('request failed');return JSONResponse({'detail':'服务暂不可用，请稍后重试'},status_code=500)
@app.get('/health')
def health():
    with Session() as db:db.execute(text('SELECT 1'))
    r=Redis.from_url(REDIS_URL,socket_timeout=2);r.ping();r.close();return {'status':'healthy'}
for r in [auth.router,stalls.router,campaigns.router,samples.router,attribution.router,analysis.router,briefs.router,catalog.router]:app.include_router(r)
