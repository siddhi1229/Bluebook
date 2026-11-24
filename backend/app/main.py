import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, inspect
from .database import Base, engine, get_db
from .models import User, Room, Examination, Assignment, BookletLog, Alert
from .schemas import Login, RoomIn, ExamIn, InvigilatorIn, AssignmentIn, IssueIn, ReturnIn
from .auth import hash_password, verify_password, token_for, current_user, coordinator
from .services.mismatch import calculate

Base.metadata.create_all(bind=engine)
if 'branch' not in {column['name'] for column in inspect(engine).get_columns('examinations')}:
    with engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE examinations ADD COLUMN branch VARCHAR(80) NOT NULL DEFAULT ''")
app=FastAPI(title='BlueBook Tracker API', version='1.0')
origins=os.getenv('FRONTEND_ORIGIN','http://localhost:5173').split(',')
app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

@app.on_event('startup')
def seed():
    db=next(get_db())
    try:
        if not db.scalar(select(User).where(User.role=='coordinator')):
            db.add(User(name='Examination Coordinator',email=os.getenv('ADMIN_EMAIL','admin@bluebook.local'),password_hash=hash_password(os.getenv('ADMIN_PASSWORD','Bluebook123!')),role='coordinator'))
            db.commit()
    finally: db.close()

def record(a):
    l=a.log
    return {'id':l.id,'assignment_id':a.id,'examination_id':a.examination_id,'exam_type':a.examination.exam_type,'semester':a.examination.semester,'branch':a.examination.branch,'academic_year':a.examination.academic_year,'subject':a.examination.subject,'exam_date':a.examination.exam_date,'room_id':a.room_id,'room_number':a.room.room_number,'invigilator_id':a.invigilator_id,'invigilator':a.invigilator.name,'booklets_issued':l.booklets_issued,'used_returned':l.used_returned,'unused_returned':l.unused_returned,'total_returned':None if l.used_returned is None else l.used_returned+l.unused_returned,'mismatch_count':l.mismatch_count,'status':l.status,'issued_at':l.issued_at,'returned_at':l.returned_at}
LOAD=[joinedload(Assignment.examination),joinedload(Assignment.room),joinedload(Assignment.invigilator),joinedload(Assignment.log)]

@app.get('/health')
def health(): return {'status':'ok'}
@app.post('/auth/login')
def login(data:Login,db:Session=Depends(get_db)):
    u=db.scalar(select(User).where(User.email==data.email.lower()))
    if not u or not verify_password(data.password,u.password_hash): raise HTTPException(401,'Email or password is incorrect')
    if not u.is_active: raise HTTPException(403,'Account is inactive')
    return {'access_token':token_for(u),'token_type':'bearer','user':{'id':u.id,'name':u.name,'email':u.email,'role':u.role}}
@app.get('/auth/me')
def me(u:User=Depends(current_user)): return {'id':u.id,'name':u.name,'email':u.email,'role':u.role}

@app.post('/rooms')
def add_room(x:RoomIn,db:Session=Depends(get_db),_:User=Depends(coordinator)):
    if db.scalar(select(Room).where(Room.room_number==x.room_number.strip())): raise HTTPException(409,'Room already exists')
    r=Room(room_number=x.room_number.strip());db.add(r);db.commit();db.refresh(r);return {'id':r.id,'room_number':r.room_number}
@app.get('/rooms')
def rooms(db:Session=Depends(get_db),_:User=Depends(current_user)): return [{'id':r.id,'room_number':r.room_number} for r in db.scalars(select(Room).order_by(Room.room_number))]
@app.put('/rooms/{id}')
def edit_room(id:int,x:RoomIn,db:Session=Depends(get_db),_:User=Depends(coordinator)):
    r=db.get(Room,id)
    if not r: raise HTTPException(404,'Room not found')
    if db.scalar(select(Room).where(Room.room_number==x.room_number.strip(),Room.id!=id)): raise HTTPException(409,'Room already exists')
    r.room_number=x.room_number.strip();db.commit();return {'id':r.id,'room_number':r.room_number}
@app.delete('/rooms/{id}')
def delete_room(id:int,db:Session=Depends(get_db),_:User=Depends(coordinator)):
    r=db.get(Room,id)
    if not r: raise HTTPException(404,'Room not found')
    if db.scalar(select(Assignment).where(Assignment.room_id==id)): raise HTTPException(409,'Room has historical assignments and cannot be deleted')
    db.delete(r);db.commit();return {'ok':True}

@app.post('/examinations')
def add_exam(x:ExamIn,db:Session=Depends(get_db),_:User=Depends(coordinator)):
    if x.exam_type not in ['CIE 1','CIE 2','CIE 3','SEE']: raise HTTPException(422,'Invalid examination type')
    e=Examination(**x.model_dump());db.add(e);db.commit();db.refresh(e);return {'id':e.id,**x.model_dump()}
@app.get('/examinations')
def exams(db:Session=Depends(get_db),_:User=Depends(current_user)): return [{'id':e.id,'semester':e.semester,'branch':e.branch,'academic_year':e.academic_year,'exam_type':e.exam_type,'subject':e.subject,'exam_date':e.exam_date} for e in db.scalars(select(Examination).order_by(Examination.exam_date.desc()))]
@app.get('/examinations/{id}')
def exam_detail(id:int,db:Session=Depends(get_db),_:User=Depends(current_user)):
    e=db.get(Examination,id)
    if not e: raise HTTPException(404,'Examination not found')
    return {'id':e.id,'semester':e.semester,'branch':e.branch,'academic_year':e.academic_year,'exam_type':e.exam_type,'subject':e.subject,'exam_date':e.exam_date}
@app.put('/examinations/{id}')
def edit_exam(id:int,x:ExamIn,db:Session=Depends(get_db),_:User=Depends(coordinator)):
    e=db.get(Examination,id)
    if not e: raise HTTPException(404,'Examination not found')
    if db.scalar(select(Assignment.id).join(BookletLog).where(Assignment.examination_id==id,BookletLog.issued_at.is_not(None))): raise HTTPException(409,'Examination cannot be edited after booklet submissions')
    for k,v in x.model_dump().items(): setattr(e,k,v)
    db.commit();return {'id':e.id,**x.model_dump()}

@app.post('/invigilators')
def add_invigilator(x:InvigilatorIn,db:Session=Depends(get_db),_:User=Depends(coordinator)):
    if db.scalar(select(User).where(User.email==x.email.lower())): raise HTTPException(409,'Email already registered')
    u=User(name=x.name,email=x.email.lower(),password_hash=hash_password(x.password),role='invigilator');db.add(u);db.commit();db.refresh(u);return {'id':u.id,'name':u.name,'email':u.email,'role':u.role,'is_active':u.is_active}
@app.get('/invigilators')
def invigilators(db:Session=Depends(get_db),_:User=Depends(coordinator)): return [{'id':u.id,'name':u.name,'email':u.email,'is_active':u.is_active} for u in db.scalars(select(User).where(User.role=='invigilator').order_by(User.name))]
@app.patch('/invigilators/{id}/status')
def status(id:int,active:bool=Query(...),db:Session=Depends(get_db),_:User=Depends(coordinator)):
    u=db.get(User,id)
    if not u or u.role!='invigilator': raise HTTPException(404,'Invigilator not found')
    u.is_active=active;db.commit();return {'id':u.id,'is_active':u.is_active}

@app.post('/assignments')
def add_assignment(x:AssignmentIn,db:Session=Depends(get_db),_:User=Depends(coordinator)):
    if not db.get(Examination,x.examination_id) or not db.get(Room,x.room_id): raise HTTPException(404,'Examination or room not found')
    u=db.get(User,x.invigilator_id)
    if not u or u.role!='invigilator' or not u.is_active: raise HTTPException(422,'Choose an active invigilator')
    if db.scalar(select(Assignment).where(Assignment.examination_id==x.examination_id,Assignment.room_id==x.room_id)): raise HTTPException(409,'Room already assigned for this examination')
    a=Assignment(**x.model_dump());a.log=BookletLog(status='PENDING');db.add(a);db.commit();db.refresh(a);return record(db.scalar(select(Assignment).options(*LOAD).where(Assignment.id==a.id)))
@app.get('/assignments')
def assignments(db:Session=Depends(get_db),_:User=Depends(coordinator)): return [record(a) for a in db.scalars(select(Assignment).options(*LOAD).order_by(Assignment.created_at.desc()))]
@app.get('/assignments/my')
def my_assignments(db:Session=Depends(get_db),u:User=Depends(current_user)):
    q=select(Assignment).options(*LOAD).order_by(Assignment.examination_id.desc())
    if u.role!='coordinator': q=q.where(Assignment.invigilator_id==u.id)
    return [record(a) for a in db.scalars(q)]
@app.get('/assignments/{id}')
def assignment(id:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    a=db.scalar(select(Assignment).options(*LOAD).where(Assignment.id==id))
    if not a: raise HTTPException(404,'Assignment not found')
    if u.role!='coordinator' and a.invigilator_id!=u.id: raise HTTPException(403,'You cannot access this assignment')
    return record(a)

@app.post('/booklets/issue')
def issue(x:IssueIn,db:Session=Depends(get_db),u:User=Depends(current_user)):
    a=db.scalar(select(Assignment).options(*LOAD).where(Assignment.id==x.assignment_id))
    if not a: raise HTTPException(404,'Assignment not found')
    if u.role!='coordinator' and a.invigilator_id!=u.id: raise HTTPException(403,'You cannot update this assignment')
    if a.log.issued_at: raise HTTPException(409,'Issue record already submitted')
    a.log.booklets_issued=x.booklets_issued;a.log.issued_at=datetime.utcnow();db.commit();return record(a)
@app.post('/booklets/return')
def return_booklets(x:ReturnIn,db:Session=Depends(get_db),u:User=Depends(current_user)):
    a=db.scalar(select(Assignment).options(*LOAD).where(Assignment.id==x.assignment_id))
    if not a: raise HTTPException(404,'Assignment not found')
    if u.role!='coordinator' and a.invigilator_id!=u.id: raise HTTPException(403,'You cannot update this assignment')
    l=a.log
    if not l.issued_at: raise HTTPException(409,'Submit issue quantities first')
    if l.returned_at: raise HTTPException(409,'Return record already finalized')
    returned,diff,state=calculate(l.booklets_issued,x.used_returned,x.unused_returned)
    l.used_returned=x.used_returned;l.unused_returned=x.unused_returned;l.mismatch_count=diff;l.status=state;l.returned_at=datetime.utcnow()
    if diff: db.add(Alert(booklet_log_id=l.id,alert_type=state,message=(f'{abs(diff)} booklet(s) remain unaccounted for.' if diff>0 else f'{abs(diff)} excess booklet(s) returned; verify the count.')))
    db.commit();return record(a)
@app.get('/booklets/logs')
def logs(db:Session=Depends(get_db),u:User=Depends(current_user),semester:int|None=None,exam_type:str|None=None,subject:str|None=None,room:str|None=None,invigilator_id:int|None=None,status_filter:str|None=None,limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)):
    q=select(Assignment).options(*LOAD).join(BookletLog)
    if u.role!='coordinator': q=q.where(Assignment.invigilator_id==u.id)
    if semester: q=q.join(Examination).where(Examination.semester==semester)
    if exam_type: q=q.join(Examination).where(Examination.exam_type==exam_type)
    if subject: q=q.join(Examination).where(Examination.subject.ilike(f'%{subject}%'))
    if room: q=q.join(Room).where(Room.room_number.ilike(f'%{room}%'))
    if invigilator_id and u.role=='coordinator': q=q.where(Assignment.invigilator_id==invigilator_id)
    if status_filter: q=q.where(BookletLog.status==status_filter.upper())
    return [record(a) for a in db.scalars(q.order_by(Assignment.created_at.desc()).offset(offset).limit(limit))]
@app.get('/booklets/{id}')
def booklet(id:int,db:Session=Depends(get_db),u:User=Depends(current_user)):
    a=db.scalar(select(Assignment).options(*LOAD).where(Assignment.id==id))
    if not a or (u.role!='coordinator' and a.invigilator_id!=u.id): raise HTTPException(404,'Booklet record not found')
    return record(a)

@app.get('/alerts')
def alerts(db:Session=Depends(get_db),_:User=Depends(coordinator)):
    rows=db.scalars(select(Alert).order_by(Alert.created_at.desc())).all();result=[]
    for z in rows:
        a=db.scalar(select(Assignment).options(*LOAD).join(BookletLog).where(BookletLog.id==z.booklet_log_id))
        result.append({'id':z.id,'alert_type':z.alert_type,'message':z.message,'created_at':z.created_at,'resolved':z.resolved,'resolved_at':z.resolved_at,'record':record(a)})
    return result
@app.patch('/alerts/{id}/resolve')
def resolve(id:int,db:Session=Depends(get_db),_:User=Depends(coordinator)):
    a=db.get(Alert,id)
    if not a: raise HTTPException(404,'Alert not found')
    a.resolved=True;a.resolved_at=datetime.utcnow();db.commit();return {'id':a.id,'resolved':True,'resolved_at':a.resolved_at}

def stats(db,eid=None):
    q=select(BookletLog,Assignment).join(Assignment,BookletLog.assignment_id==Assignment.id)
    if eid: q=q.where(Assignment.examination_id==eid)
    rows=db.execute(q).all();issued=sum((l.booklets_issued or 0) for l,a in rows);returned=sum((l.used_returned or 0)+(l.unused_returned or 0) for l,a in rows if l.returned_at);pending=sum(1 for l,a in rows if not l.returned_at);bad=sum(1 for l,a in rows if l.status in ('MISMATCH','EXCESS_RETURN'))
    unaccounted=sum((l.mismatch_count or 0) for l,a in rows if l.returned_at)
    return {'total_issued':issued,'total_returned':returned,'total_unaccounted':unaccounted,'rooms_with_mismatches':bad,'pending_submissions':pending,'matched_rooms':sum(l.status=='MATCHED' for l,a in rows),'total_assignments':len(rows)}
@app.get('/dashboard/summary')
def dashboard(db:Session=Depends(get_db),_:User=Depends(coordinator)):
    s=stats(db);recent=[record(a) for a in db.scalars(select(Assignment).options(*LOAD).order_by(Assignment.created_at.desc()).limit(6))]
    alerts_open=db.scalar(select(func.count(Alert.id)).where(Alert.resolved.is_(False)))
    return {**s,'open_alerts':alerts_open,'recent_records':recent,'recent_examinations':[{'id':e.id,'exam_type':e.exam_type,'subject':e.subject,'branch':e.branch,'exam_date':e.exam_date} for e in db.scalars(select(Examination).order_by(Examination.created_at.desc()).limit(5))]}

async def gemini(prompt):
    key=os.getenv('GEMINI_API_KEY')
    if not key: return 'AI summary is unavailable because GEMINI_API_KEY is not configured. Verified application figures are shown above.'
    try:
        from google import genai
        client=genai.Client(api_key=key)
        response=client.models.generate_content(model=os.getenv('GEMINI_MODEL','gemini-2.5-flash'),contents=prompt)
        return response.text or 'AI did not return a summary.'
    except Exception: return 'AI summary is temporarily unavailable. Verified application figures are shown above.'
@app.post('/ai/mismatch-explanation')
async def mismatch_ai(assignment_id:int,db:Session=Depends(get_db),_:User=Depends(coordinator)):
    a=db.scalar(select(Assignment).options(*LOAD).where(Assignment.id==assignment_id))
    if not a or not a.log.returned_at: raise HTTPException(404,'Finalized booklet record not found')
    r=record(a);return {'explanation':await gemini(f"Briefly explain this verified discrepancy and recommend a verification action. Data: {r}")}
@app.post('/ai/examination-summary')
async def exam_ai(examination_id:int,db:Session=Depends(get_db),_:User=Depends(coordinator)):
    e=db.get(Examination,examination_id)
    if not e: raise HTTPException(404,'Examination not found')
    s=stats(db,examination_id);return {'statistics':s,'summary':await gemini(f"Write a concise examination booklet reconciliation summary. Do not recalculate. Verified statistics: {s}; examination: {e.exam_type} {e.subject}, semester {e.semester}.")}
