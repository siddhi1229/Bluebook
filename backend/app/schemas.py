from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator

def valid_email(value: str) -> str:
    value = value.strip().lower()
    if '@' not in value or '.' not in value.rsplit('@', 1)[-1]:
        raise ValueError('Enter a valid email address')
    return value

class Login(BaseModel):
    email: str
    password: str
    _email = field_validator('email')(valid_email)
class UserOut(BaseModel): model_config=ConfigDict(from_attributes=True); id:int; name:str; email:str; role:str; is_active:bool
class RoomIn(BaseModel): room_number:str=Field(min_length=1,max_length=40)
class ExamIn(BaseModel): semester:int=Field(ge=1,le=12); branch:str=Field(min_length=1,max_length=80); academic_year:str; exam_type:str; subject:str=Field(min_length=1); exam_date:date
class InvigilatorIn(BaseModel):
    name:str
    email:str
    password:str=Field(min_length=8)
    _email = field_validator('email')(valid_email)
class AssignmentIn(BaseModel): examination_id:int; room_id:int; invigilator_id:int
class IssueIn(BaseModel): assignment_id:int; booklets_issued:int=Field(gt=0)
class ReturnIn(BaseModel): assignment_id:int; used_returned:int=Field(ge=0); unused_returned:int=Field(ge=0)
