from datetime import datetime, date
from sqlalchemy import String, Integer, Boolean, DateTime, Date, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default='invigilator')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Room(Base):
    __tablename__ = 'rooms'
    id: Mapped[int] = mapped_column(primary_key=True)
    room_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)

class Examination(Base):
    __tablename__ = 'examinations'
    id: Mapped[int] = mapped_column(primary_key=True)
    semester: Mapped[int] = mapped_column(Integer)
    branch: Mapped[str] = mapped_column(String(80), default='')
    academic_year: Mapped[str] = mapped_column(String(20))
    exam_type: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(150))
    exam_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Assignment(Base):
    __tablename__ = 'assignments'
    __table_args__ = (UniqueConstraint('examination_id','room_id', name='uq_exam_room'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    examination_id: Mapped[int] = mapped_column(ForeignKey('examinations.id'))
    room_id: Mapped[int] = mapped_column(ForeignKey('rooms.id'))
    invigilator_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    examination = relationship('Examination')
    room = relationship('Room')
    invigilator = relationship('User')
    log = relationship('BookletLog', back_populates='assignment', uselist=False, cascade='all, delete-orphan')

class BookletLog(Base):
    __tablename__ = 'booklet_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey('assignments.id'), unique=True)
    booklets_issued: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_returned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unused_returned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mismatch_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(24), default='PENDING')
    issued_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    assignment = relationship('Assignment', back_populates='log')

class Alert(Base):
    __tablename__ = 'alerts'
    id: Mapped[int] = mapped_column(primary_key=True)
    booklet_log_id: Mapped[int] = mapped_column(ForeignKey('booklet_logs.id'), index=True)
    alert_type: Mapped[str] = mapped_column(String(30))
    message: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
