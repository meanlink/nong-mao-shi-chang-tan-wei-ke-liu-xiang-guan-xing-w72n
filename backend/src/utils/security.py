import hashlib,hmac,secrets,time,jwt
from src.config.settings import JWT_SECRET
def hash_password(password):
    salt=secrets.token_hex(16); return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),120000).hex()
def verify_password(password,stored):
    salt,digest=stored.split(':',1); return hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),120000).hex(),digest)
def token_for(user): return jwt.encode({'sub':str(user.id),'exp':int(time.time())+28800},JWT_SECRET,algorithm='HS256')
def decode_token(token): return int(jwt.decode(token,JWT_SECRET,algorithms=['HS256'])['sub'])
