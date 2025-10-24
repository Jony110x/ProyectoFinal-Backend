from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models.modelo import User, session, UpdateUserInput
from passlib.context import CryptContext

updateUser = APIRouter()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@updateUser.put("/update-profile")
def update_user(data: UpdateUserInput):
    try:
        user_db = session.query(User).filter(User.id == data.id).first()

        if not user_db:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

        existing_user = session.query(User).filter(User.username == data.username, User.id != data.id).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso")

        user_db.username = data.username
        user_db.password = data.password

        session.commit()

        return {
            "status": "success",
            "message": "Usuario actualizado correctamente",
            "user": {
                "id": user_db.id,
                "username": user_db.username,              
            }
        }

    except Exception as e:
        session.rollback()
        print("Error actualizando usuario:", e)
        raise HTTPException(status_code=500, detail="Error interno")
    finally:
        session.close()
