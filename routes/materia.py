from fastapi import APIRouter
from models.modelo import Materia, Carer, InputMateria, session, User, alumno_materia, profesor_materia
from pydantic import BaseModel, conint
from typing import List, Optional 
 

materia = APIRouter()

class NotaInput(BaseModel):
    user_id: int
    nota: Optional[conint(ge=1, le=10)] = None # type: ignore

@materia.post("/materia/new")
def crear_materia(data: InputMateria):
    try:
        carer = session.query(Carer).filter_by(id=data.carer_id).first()
        if not carer:
            return {"error": "Carrera no encontrada"}

        nueva_materia = Materia(name=data.name, carer_id=data.carer_id)
        session.add(nueva_materia)
        session.commit()

        return {"mensaje": f"Materia '{data.name}' creada en la carrera '{carer.name}'"}
    except Exception as e:
        session.rollback()
        return {"error": str(e)}
    finally:
        session.close()


@materia.get("/materia/{career_id}/all")
def all_materia(career_id: int):
    return session.query(Materia).filter(Materia.carer_id == career_id).all()


@materia.put("/materia/{materia_id}/edit")
def editar_materia(materia_id: int, payload: dict):
    materia = session.query(Materia).filter(Materia.id == materia_id).first()
    if not materia:
        return {"status": "error", "message": "Materia no encontrada"}
    materia.name = payload.get("name", materia.name)
    session.commit()
    return {"status": "success", "message": "Materia actualizada"}


@materia.delete("/materia/{materia_id}/delete")
def borrar_materia(materia_id: int):
    materia = session.query(Materia).filter(Materia.id == materia_id).first()
    if not materia:
        return {"status": "error", "message": "Materia no encontrada"}
    session.delete(materia)
    session.commit()
    return {"status": "success", "message": "Materia eliminada"}


@materia.post("/materia/{materia_id}/notas")
def guardar_notas(materia_id: int, notas: List[NotaInput]):
    for n in notas:
        if n.nota is not None:  # Evitar nulls
            stmt = (
                alumno_materia.update()
                .where(
                    (alumno_materia.c.user_id == n.user_id) &
                    (alumno_materia.c.materia_id == materia_id)
                )
                .values(nota=n.nota)
            )
            session.execute(stmt)

    session.commit()
    return {"status": "success", "message": "Notas actualizadas"}


@materia.get("/materia/{materia_id}/estudiantes")
def obtener_estudiantes_por_materia(materia_id: int):
    materia = session.query(Materia).filter(Materia.id == materia_id).first()
    if not materia:
        return {"status": "error", "message": "Materia no encontrada"}

    estudiantes = []

    # Hacemos un join entre usuarios y la tabla alumno_materia
    query = session.query(User, alumno_materia.c.nota).\
    join(alumno_materia, alumno_materia.c.user_id == User.id).\
    filter(alumno_materia.c.materia_id == materia_id)
    print(query.all())

    for user, nota in query:
     estudiantes.append({
        "id": user.id,
        "nombre": user.userdetail.firstName if user.userdetail else "",
        "apellido": user.userdetail.lastName,
        "username": user.username,
        "DNI": user.userdetail.dni,
        "email":user.userdetail.email,
        "nota": nota
    })

    return {"status": "success", "estudiantes": estudiantes}


@materia.get("/materia/{materia_id}/{user_id}")
def obtener_nota_estudiante(materia_id: int, user_id: int):
    try:
        # Buscar la nota del estudiante en la materia
        stmt = (
            alumno_materia.select()
            .where(
                (alumno_materia.c.user_id == user_id) &
                (alumno_materia.c.materia_id == materia_id)
            )
        )
        result = session.execute(stmt).first()

        if result is None:
            return {"status": "error", "message": "Nota no encontrada"}

        return {
            "status": "success",
            "materia_id": materia_id,
            "user_id": user_id,
            "nota": result.nota
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
    

@materia.get("/asignadas")
def obtener_materias_con_profesor():
    try:
        result = session.query(profesor_materia).all()

        # result es una lista de Row (tuplas), por eso usamos índices
        asignadas = [{"materia_id": row[1], "profesor_id": row[0]} for row in result]

        return asignadas
    except Exception as e:
        return {"status": "error", "message": str(e)}