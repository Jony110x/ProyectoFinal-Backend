from fastapi import APIRouter
from fastapi.responses import JSONResponse
from models.modelo import Carer, InputCarer, session, Materia

carer = APIRouter()

@carer.get("/carer/all")
def get_carers():
    return session.query(Carer).all()


@carer.post("/carer/new")
def new_carer(ca: InputCarer):
    try:
        newCarer = Carer(ca.name)
        session.add(newCarer)
        session.commit()
        res = "carrera "+ca.name +" guardada correctamente"
        print(res)
        return {"mensaje": res}
    except Exception as ex:
        session.rollback()
        print("Error al agregar carrera -->>", ex)
        return {"error": str(ex)}
    finally:
        session.close()


@carer.put("/career/{career_id}/edit")
def editar_carrera(career_id: int, payload: dict):
    carrera = session.query(Carer).filter(Carer.id == career_id).first()
    if not carrera:
        return {"status": "error", "message": "Carrera no encontrada"}
    carrera.name = payload.get("name", carrera.name)
    session.commit()
    return {"status": "success", "message": "Carrera actualizada"}


@carer.delete("/career/{career_id}/delete")
def borrar_carrera(career_id: int):
    carrera = session.query(Carer).filter(Carer.id == career_id).first()
    if not carrera:
        return {"status": "error", "message": "Carrera no encontrada"}
    session.delete(carrera)
    session.commit()
    return {"status": "success", "message": "Carrera eliminada"}


@carer.delete("/career/{career_id}/delete")
def borrar_carrera(career_id: int):
    carrera = session.query(Carer).filter(Carer.id == career_id).first()
    if not carrera:
        return {"status": "error", "message": "Carrera no encontrada"}

    # Eliminar materias asociadas a la carrera
    materias = session.query(Materia).filter(Materia.carer_id == career_id).all()
    for materia in materias:
        session.delete(materia)

    # Eliminar la carrera
    session.delete(carrera)
    session.commit()

    return {"status": "success", "message": "Carrera y materias eliminadas correctamente"}

