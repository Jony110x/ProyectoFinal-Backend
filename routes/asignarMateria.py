from fastapi import APIRouter
from models.modelo import Materia, InputAsignarMateria, session, User, UserDetails, profesor_materia
from sqlalchemy.orm import joinedload

asignar = APIRouter()

@asignar.post("/users/asignar-materia")
def asignar_materia(data: InputAsignarMateria):
    try:
        usuario = session.query(User).filter(User.id == data.user_id).first()
        materia = session.query(Materia).filter(Materia.id == data.materia_id).first()
        
        if not usuario or not materia:
            return {"status": "error", "message": "Usuario o materia no encontrados"}
        
        # Verificar el tipo de usuario
        if data.tipo_relacion == "estudiante" and usuario.userdetail.type == "estudiante":
            if materia not in usuario.materias_como_alumno:
                usuario.materias_como_alumno.append(materia)
        elif data.tipo_relacion == "profesor" and usuario.userdetail.type == "profesor":
            if materia not in usuario.materias_como_profesor:
                usuario.materias_como_profesor.append(materia)
        else:
            return {"status": "error", "message": "Tipo de relación no válido para este usuario"}
        
        session.commit()
        return {"status": "success", "message": "Materia asignada correctamente"}
        
    except Exception as e:
        session.rollback()
        return {"status": "error", "message": str(e)}


@asignar.get("/users/{user_id}/materias")
def obtener_materias_usuario(user_id: int):
    try:
        usuario = session.query(User).filter(User.id == user_id).first()
        
        if not usuario:
            return {"status": "error", "message": "Usuario no encontrado"}
        
        materias = []
        if usuario.userdetail.type == "estudiante":
            materias = [{"id": m.id, "name": m.name, "career": m.carer.name if m.carer else "Sin carrera"} 
                       for m in usuario.materias_como_alumno]
        elif usuario.userdetail.type == "profesor":
            materias = [{"id": m.id, "name": m.name, "career": m.carer.name if m.carer else "Sin carrera"} 
                       for m in usuario.materias_como_profesor]
        
        return {
            "status": "success", 
            "materias": materias
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@asignar.get("/materia/{materia_id}/estudiantes")
def obtener_estudiantes_por_materia(materia_id: int):
    try:
        # Buscar materia
        materia = session.query(Materia).filter(Materia.id == materia_id).first()
        if not materia:
            return {"status": "error", "message": "Materia no encontrada"}

        # Filtrar solo usuarios de tipo estudiante
        estudiantes = [
            {
                "id": u.id,
                "username": u.username,
                "nombre": f"{u.userdetail.firstName} {u.userdetail.lastName}" if u.userdetail else "",
            }
            for u in materia.alumnos
            if u.userdetail and u.userdetail.type == "estudiante"
        ]

        return {"status": "success", "estudiantes": estudiantes}

    except Exception as e:
        return {"status": "error", "message": str(e)}  


@asignar.get("/users/{user_id}/profesor")
def obtener_materias_con_profesor(user_id: int):
    try:
        usuario = session.query(User).options(joinedload(User.userdetail)).filter(User.id == user_id).first()

        if not usuario:
            return {"status": "error", "message": "Usuario no encontrado"}

        materias = []

        if usuario.userdetail.type == "estudiante":
            for materia in usuario.materias_como_alumno:
                # Buscar profesor de esa materia desde la tabla profesor_materia
                profesor_data = (
                    session.query(User)
                    .join(UserDetails)
                    .join(profesor_materia, profesor_materia.c.user_id == User.id)
                    .filter(profesor_materia.c.materia_id == materia.id)
                    .first()
                )

                materias.append({
                    "id": materia.id,
                    "name": materia.name,
                    "career": materia.carer.name if materia.carer else "Sin carrera",
                    "profesor": {
                        "id": profesor_data.id,
                        "username": profesor_data.username,
                        "firstName": profesor_data.userdetail.firstName,
                        "lastName": profesor_data.userdetail.lastName
                    } if profesor_data else None
                })

        elif usuario.userdetail.type == "profesor":
            for materia in usuario.materias_como_profesor:
                materias.append({
                    "id": materia.id,
                    "name": materia.name,
                    "career": materia.carer.name if materia.carer else "Sin carrera",
                    "profesor": {
                        "id": usuario.id,
                        "username": usuario.username,
                        "firstName": usuario.userdetail.firstName,
                        "lastName": usuario.userdetail.lastName
                    }
                })

        return {
            "status": "success",
            "materias": materias
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
