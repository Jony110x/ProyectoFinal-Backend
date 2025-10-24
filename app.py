import sys  
sys.tracebacklimit = 1  

from fastapi import FastAPI
from routes.user import user
from routes.payment import payment
from fastapi.middleware.cors import CORSMiddleware
from routes.carer import carer
from routes.materia import materia
from routes.updateUser import updateUser
from routes.message import message
from routes.asignarMateria import asignar
from fastapi.staticfiles import StaticFiles

api_escu = FastAPI()

api_escu.include_router(user)

api_escu.include_router(payment)

api_escu.include_router(carer)

api_escu.include_router(materia)

api_escu.include_router(updateUser)

api_escu.include_router(message)

api_escu.include_router(asignar)

api_escu.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"]
)

api_escu.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
