import os, jwt, hashlib, secrets, base64
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

SECRET=os.getenv('JWT_SECRET','change-this-secret-before-deployment')
oauth=OAuth2PasswordBearer(tokenUrl='/auth/login')
def hash_password(value):
    salt=secrets.token_bytes(16)
    digest=hashlib.scrypt(value.encode(),salt=salt,n=2**14,r=8,p=1)
    return 'scrypt$'+base64.b64encode(salt).decode()+'$'+base64.b64encode(digest).decode()
def verify_password(value, hashed):
    try:
        scheme,salt,digest=hashed.split('$')
        if scheme!='scrypt': return False
        actual=hashlib.scrypt(value.encode(),salt=base64.b64decode(salt),n=2**14,r=8,p=1)
        return secrets.compare_digest(actual,base64.b64decode(digest))
    except Exception: return False
def token_for(user): return jwt.encode({'sub':str(user.id),'exp':datetime.utcnow()+timedelta(hours=12)},SECRET,algorithm='HS256')
def current_user(token:str=Depends(oauth), db:Session=Depends(get_db)):
    try: uid=jwt.decode(token,SECRET,algorithms=['HS256'])['sub']
    except Exception: raise HTTPException(401,'Invalid or expired session')
    user=db.get(User,int(uid))
    if not user or not user.is_active: raise HTTPException(401,'Account is inactive')
    return user
def coordinator(user:User=Depends(current_user)):
    if user.role!='coordinator': raise HTTPException(403,'Coordinator access required')
    return user
