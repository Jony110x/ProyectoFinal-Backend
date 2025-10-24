from typing import Any, Dict, Optional
from config.db import engine, Base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Table, Text
from sqlalchemy.orm import sessionmaker, relationship
from pydantic import BaseModel, Field
import datetime

# Tabla intermedia para alumnos y materias (muchos a muchos)
alumno_materia = Table('alumno_materia', Base.metadata,
    Column('user_id', Integer, ForeignKey('usuarios.id')),
    Column('materia_id', Integer, ForeignKey('materia.id')),
    Column('nota', Integer, nullable=True)
)

# Tabla intermedia para profesores y materias (muchos a muchos)
profesor_materia = Table('profesor_materia', Base.metadata,
    Column('user_id', Integer, ForeignKey('usuarios.id')),
    Column('materia_id', Integer, ForeignKey('materia.id'))
)

class User(Base):
    __tablename__ = "usuarios"

    id = Column("id", Integer, primary_key=True, index=True, autoincrement=True)
    username = Column("username", String(50), unique=True, nullable=False)
    password = Column("password", String(50))
    id_userdetail = Column(Integer, ForeignKey("userdetails.id"))
    
    # Relaciones
    userdetail = relationship("UserDetails", back_populates="user", uselist=False)
    payments = relationship("Payment", uselist=True, back_populates="user")
    
    # Relaciones para materias según tipo de usuario
    materias_como_alumno = relationship("Materia", secondary=alumno_materia, back_populates="alumnos")
    materias_como_profesor = relationship("Materia", secondary=profesor_materia, back_populates="profesores")

    def __init__(self, username, password):
        self.username = username
        self.password = password

class UserDetails(Base):
    __tablename__ = "userdetails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dni = Column(Integer, unique=True)
    firstName = Column(String(50))
    lastName = Column(String(50))
    type = Column(String)
    email = Column(String, nullable=False, unique=True)
    carer_id = Column(Integer, ForeignKey("carer.id"), nullable=True)
    carer = relationship("Carer", back_populates="estudiantes")
    user = relationship("User", back_populates="userdetail")

    def __init__(self, dni, firstName, lastName, type, email, carer_id=None):
        self.dni = dni
        self.firstName = firstName
        self.lastName = lastName
        self.type = type
        self.email = email
        self.carer_id = carer_id

class Materia(Base):
    __tablename__ = "materia"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    carer_id = Column(Integer, ForeignKey("carer.id"))

    # Relaciones
    carer = relationship("Carer", back_populates="materias")
    alumnos = relationship("User", secondary=alumno_materia, back_populates="materias_como_alumno")
    profesores = relationship("User", secondary=profesor_materia, back_populates="materias_como_profesor")

class Carer(Base):
    __tablename__ = "carer"

    id = Column("id", Integer, primary_key=True)
    name = Column(String(50))

    # Relaciones
    materias = relationship("Materia", back_populates="carer")
    estudiantes = relationship("UserDetails", back_populates="carer")

    def __init__(self, name):
        self.name = name

class Payment(Base):
    __tablename__ = "payments"

    id = Column("id", Integer, primary_key=True)
    carer_id = Column(ForeignKey("carer.id"), nullable=False)
    user_id = Column(ForeignKey("usuarios.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    affected_month = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

    # Relaciones
    user = relationship("User", uselist=False, back_populates="payments")
    carer = relationship("Carer", uselist=False)

class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow) 
    file_url = Column(String, nullable=True)


    sender = relationship("User", foreign_keys=[sender_id])
    receiver = relationship("User", foreign_keys=[receiver_id])



# Actualizar modelos Pydantic
class InputUserDetail(BaseModel):
    dni: int
    firstName: str
    lastName: str
    type: str
    email: str
    carer_id: int = None  # Opcional para alumnos

class InputUser(BaseModel):
    username: str
    password: str
    email: str
    dni: int
    firstName: str
    lastName: str
    type: str
    carer_id: int = None  # Opcional para alumnos

class InputLogin(BaseModel):
    username: str
    password: str

class InputCarer(BaseModel):
    name: str

class InputPayment(BaseModel):
    carer_id: int
    user_id: int
    amount: int
    affected_month: datetime.date 

class UpdatePayment(BaseModel):
    carer_id: int
    amount: int
    affected_month: datetime.date   

class InputMateria(BaseModel):
    name: str
    carer_id: int

class InputAsignarMateria(BaseModel):
    user_id: int
    materia_id: int
    tipo_relacion: str  # "alumno" o "profesor"

class UpdateUserInput(BaseModel):
    id: int
    username: str
    password: str

class InputMessage(BaseModel):
    sender_id: int
    receiver_id: int
    content: str
    file_url: Optional[str] = None

class MessageOut(BaseModel):
    id: int
    sender_id: int
    receiver_id: int
    content: str
    timestamp: datetime.datetime    
    file_url: Optional[str] = None

    class Config:
        from_attributes = True

class InputPaginatedRequest(BaseModel):
    limit: int = 20
    last_seen_id: Optional[int] = None


# Crear las tablas
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
session = Session()



# **********hecho con el profe********
class InputPaginatedRequestFilter(BaseModel):
    limit: int = Field(
        20, gt=0, le=100, description="Cantidad maxima de registros a retornar"
    )
    last_seen_id: Optional[int] = Field(
        None, description=" id de ultimo registro visto (cursor) para el keyset pagination"
    )
    filters: Optional[Dict[str, Any]] = Field(None, description="Filtros de algo")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

ASYNC_DATABASE_URL = "postgresql+asyncpg://postgres:1234@localhost:5432/proyectoFinal-copia"

async_engine = create_async_engine(ASYNC_DATABASE_URL, echo=False)

AsyncSessionLocal = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

