import time
from collections import defaultdict,deque
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
class RequestControl(BaseHTTPMiddleware):
    def __init__(self,app): super().__init__(app); self.events=defaultdict(deque)
    async def dispatch(self,request:Request,call_next):
        if request.url.path=='/health': return await call_next(request)
        key=request.client.host if request.client else 'unknown'; now=time.monotonic(); q=self.events[key]
        while q and now-q[0]>10:q.popleft()
        if len(q)>=80:return JSONResponse({'detail':'请求过于频繁，请稍后再试'},status_code=429)
        q.append(now); return await call_next(request)
