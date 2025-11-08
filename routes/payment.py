from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import String, extract
from auth.security import Security
from models.modelo import Payment, InputPayment, UserDetails, session, User, Carer, UpdatePayment, InputPaginatedRequest
from sqlalchemy.orm import joinedload

payment = APIRouter()


@payment.get("/payment/all")
def get_all_payments():
    try:
        pagos = session.query(Payment).options(joinedload(Payment.user).joinedload(User.userdetail)).all()
        resultados = []
        for pago in pagos:
            resultados.append({
                "id": pago.id,
                "amount": pago.amount,
                "affected_month": str(pago.affected_month),
                "carer": pago.carer.name if pago.carer else None,
                "carer_id":pago.carer.id,
                "username":pago.user.username,
                "user": {
                    "id": pago.user_id,
                    "userdetail": {
                        "firstName": pago.user.userdetail.firstName,
                        "lastName": pago.user.userdetail.lastName,
                    } if pago.user and pago.user.userdetail else None
                } if pago.user else None,
            })
        return resultados
    except Exception as e:
        print("Error:", e)
        return JSONResponse(status_code=500, content={"detail": "Error al obtener pagos"})


@payment.post("/payment/new")
def create_payment(data: InputPayment):
    try:
        user = session.query(User).options(
            joinedload(User.userdetail)
        ).filter(User.id == data.user_id).first()
        carer = session.query(Carer).filter(Carer.id == data.carer_id).first()

        if not user:
            return JSONResponse(status_code=404, content={"detail": "Usuario no encontrado"})
        if not user.userdetail:
            return JSONResponse(status_code=400, content={"detail": "El usuario no tiene detalles"})
        if not carer:
            return JSONResponse(status_code=404, content={"detail": "Materia no encontrada"})

        nuevo = Payment(
            carer_id=data.carer_id,
            user_id=data.user_id,
            amount=data.amount,
            affected_month=data.affected_month
        )
        session.add(nuevo)
        session.commit()
        session.refresh(nuevo)

        return {
            "id": nuevo.id,
            "amount": nuevo.amount,
            "affected_month": str(nuevo.affected_month),
            "carer": carer.name,
            "user": {
                "id": user.id,
                "userdetail": {
                    "firstName": user.userdetail.firstName,
                    "lastName": user.userdetail.lastName,
                }
            }
        }

    except Exception as e:
        session.rollback()
        print("Error al crear pago:", e)
        return JSONResponse(status_code=500, content={"detail": "Error interno al crear pago"})
    finally:
        session.close()

    
@payment.get("/payment/user/{username}")
def payment_user(username: str):
    try:
        user = session.query(User).options(joinedload(User.userdetail)).filter(User.username == username).first()

        if not user:
            return JSONResponse(status_code=404, content={"detail": "Usuario no encontrado"})

        pagos = (
            session.query(Payment)
            .options(joinedload(Payment.carer), joinedload(Payment.user).joinedload(User.userdetail))
            .filter(Payment.user_id == user.id)
            .all()
        )

        resultados = []
        for pago in pagos:
            resultados.append({
                "id": pago.id,
                "amount": pago.amount,
                "affected_month": str(pago.affected_month),
                "carer": pago.carer.name if pago.carer else None,
                "username": user.username 
            })

        return resultados

    except Exception as ex:
        print("Error al traer pagos:", ex)
        return JSONResponse(status_code=500, content={"detail": "Error interno"})
    finally:
        session.close()


@payment.put("/payment/{payment_id}")
def actualizar_pago(payment_id: int, data: UpdatePayment):
    pago = session.query(Payment).get(payment_id)
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")

    pago.carer_id = data.carer_id
    pago.amount = data.amount
    pago.affected_month = data.affected_month

    session.commit()
    return {"message": "Pago actualizado correctamente"}


@payment.delete("/payment/{payment_id}")
def eliminar_pago(payment_id: int):
    pago = session.query(Payment).get(payment_id)
    if not pago:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    
    session.delete(pago)
    session.commit()
    return {"message": "Pago eliminado correctamente"}  


@payment.get("/payment/pending")
def get_usuarios_con_pagos_pendientes():
    try:
        from datetime import datetime
        mes_actual = datetime.now().month
        anio_actual = datetime.now().year
        
        # Obtener todos los estudiantes con sus detalles y carrera
        estudiantes = (
            session.query(User)
            .options(
                joinedload(User.userdetail).joinedload(UserDetails.carer)
            )
            .join(UserDetails)
            .filter(UserDetails.type == "estudiante")
            .all()
        )
        
        # Obtener pagos del mes actual
        pagos_mes = (
            session.query(Payment)
            .filter(
                extract('month', Payment.affected_month) == mes_actual,
                extract('year', Payment.affected_month) == anio_actual
            )
            .all()
        )
        
        # Set de usuarios que ya pagaron
        usuarios_con_pago = {pago.user_id for pago in pagos_mes}
        
        # Construir lista de deudores
        usuarios_pendientes = []
        for estudiante in estudiantes:
            if estudiante.id not in usuarios_con_pago and estudiante.userdetail:
                # Obtener última carrera del último pago o la asignada en userdetail
                ultima_carrera = None
                
                # Primero intentar obtener del último pago
                ultimo_pago = (
                    session.query(Payment)
                    .filter(Payment.user_id == estudiante.id)
                    .order_by(Payment.affected_month.desc())
                    .first()
                )
                
                if ultimo_pago and ultimo_pago.carer:
                    ultima_carrera = ultimo_pago.carer.name
                elif estudiante.userdetail.carer:
                    ultima_carrera = estudiante.userdetail.carer.name
                else:
                    ultima_carrera = "Sin carrera asignada"
                
                # Contar cuántos meses debe
                total_pagos = (
                    session.query(Payment)
                    .filter(Payment.user_id == estudiante.id)
                    .count()
                )
                
                usuarios_pendientes.append({
                    "id": estudiante.id,
                    "username": estudiante.username,
                    "firstName": estudiante.userdetail.firstName,
                    "lastName": estudiante.userdetail.lastName,
                    "fullname": f"{estudiante.userdetail.firstName} {estudiante.userdetail.lastName}",
                    "email": estudiante.userdetail.email,
                    "dni": estudiante.userdetail.dni,
                    "carer": ultima_carrera,
                    "carer_id": estudiante.userdetail.carer_id,
                    "total_pagos_realizados": total_pagos
                })
        
        return {
            "count": len(usuarios_pendientes),
            "month": mes_actual,
            "year": anio_actual,
            "deudores": usuarios_pendientes
        }
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": "Error interno"})
    finally:
        session.close()



@payment.post("/payment/paginated")
async def get_payments_paginated(
    req: Request,
    body: InputPaginatedRequest
):
    try:
        # Verificar token
        has_access = Security.verify_token(req.headers)
        if "iat" not in has_access:
            return JSONResponse(status_code=401, content=has_access)

        limit = body.limit
        last_seen_id = body.last_seen_id
        user_id = getattr(body, "user_id", None)
        start_date = getattr(body, "start_date", None)
        end_date = getattr(body, "end_date", None)

        # Query base con join para traer usuario y carrera
        query = (
            session.query(Payment, User.username, Carer.name.label("carer_name"))
            .join(User, Payment.user_id == User.id)
            .join(Carer, Payment.carer_id == Carer.id)
            .order_by(Payment.id)
        )

        # Filtro por last_seen_id (cursor)
        if last_seen_id is not None:
            query = query.filter(Payment.id > last_seen_id)

        # Filtro por usuario
        if user_id:
            query = query.filter(Payment.user_id == user_id)

        # Filtro por rango de fechas (created_at)
        if start_date and end_date:
            query = query.filter(Payment.created_at.between(start_date, end_date))
        elif start_date:
            query = query.filter(Payment.created_at >= start_date)
        elif end_date:
            query = query.filter(Payment.created_at <= end_date)

        # Ejecutar query con límite
        resultados = query.limit(limit).all()

        # Serializar resultados
        pagos_data = []
        for payment, username, carer_name in resultados:
            pagos_data.append({
                "id": payment.id,
                "user_id": payment.user_id,
                "username": username,
                "carer_id": payment.carer_id,
                "carer": carer_name,
                "amount": payment.amount,
                "affected_month": payment.affected_month.strftime("%Y-%m-%d"),
                "created_at": payment.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })

        next_cursor = pagos_data[-1]["id"] if len(pagos_data) == limit else None

        return JSONResponse(
            status_code=200,
            content={"payments": pagos_data, "next_cursor": next_cursor}
        )

    except Exception as ex:
        session.rollback()
        print("Error al obtener pagos paginados:", ex)
        return JSONResponse(
            status_code=500,
            content={"message": "Error al obtener pagos paginados"}
        )


@payment.get("/payment/search")
def search_payments(
    q: str, 
    limit: int = 20, 
    offset: int = 0, 
    user_id: Optional[int] = None,  # ← AGREGAR ESTE PARÁMETRO
    req: Request = None
):
    try:
        # Verificar token
        has_access = Security.verify_token(req.headers)
        if "iat" not in has_access:
            return JSONResponse(status_code=401, content=has_access)

        # Query base
        query = (
            session.query(Payment, User.username, Carer.name.label("carer_name"))
            .join(User, Payment.user_id == User.id)
            .join(Carer, Payment.carer_id == Carer.id)
        )

        # ✅ FILTRO POR USER_ID (NUEVO)
        if user_id is not None:
            query = query.filter(Payment.user_id == user_id)

        # Filtro por término de búsqueda (usuario o materia)
        q_like = f"%{q}%"
        query = query.filter(
            (User.username.ilike(q_like)) |
            (User.userdetail.has(UserDetails.firstName.ilike(q_like))) |
            (User.userdetail.has(UserDetails.lastName.ilike(q_like))) |
            (Carer.name.ilike(q_like))
        )

        # Orden y paginación
        query = query.order_by(Payment.id).limit(limit).offset(offset)

        resultados = query.all()

        pagos_data = []
        for payment, username, carer_name in resultados:
            pagos_data.append({
                "id": payment.id,
                "user_id": payment.user_id,
                "username": username,
                "carer_id": payment.carer_id,
                "carer": carer_name,
                "amount": payment.amount,
                "affected_month": payment.affected_month.strftime("%Y-%m-%d"),
                "created_at": payment.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })

        return {"payments": pagos_data}

    except Exception as e:
        session.rollback()
        print("Error buscando pagos:", e)
        return JSONResponse(status_code=500, content={"detail": "Error interno"})
    

@payment.get("/payment/pending")
def get_usuarios_con_pagos_pendientes(
    limit: int = 50,
    last_seen_id: Optional[int] = None
):
    try:
        from datetime import datetime
        mes_actual = datetime.now().month
        anio_actual = datetime.now().year
        
        # Obtener pagos del mes actual
        pagos_mes = (
            session.query(Payment.user_id)
            .filter(
                extract('month', Payment.affected_month) == mes_actual,
                extract('year', Payment.affected_month) == anio_actual
            )
            .distinct()
            .all()
        )
        
        # Set de usuarios que ya pagaron
        usuarios_con_pago = {pago.user_id for pago in pagos_mes}
        
        # Query base de estudiantes deudores
        estudiantes_query = (
            session.query(User)
            .options(
                joinedload(User.userdetail).joinedload(UserDetails.carer)
            )
            .join(UserDetails)
            .filter(UserDetails.type == "estudiante")
            .order_by(User.id.asc())  # Importante: ordenar por ID para cursor
        )
        
        # Si hay cursor, empezar desde ahí
        if last_seen_id is not None:
            estudiantes_query = estudiantes_query.filter(User.id > last_seen_id)
        
        # Traer limit + 1 para saber si hay más
        estudiantes = estudiantes_query.limit(limit + 1).all()
        
        # Filtrar los que NO pagaron este mes
        estudiantes_deudores = [
            est for est in estudiantes
            if est.id not in usuarios_con_pago and est.userdetail
        ]
        
        # Verificar si hay más resultados
        has_more = len(estudiantes_deudores) > limit
        if has_more:
            estudiantes_deudores = estudiantes_deudores[:limit]
        
        # Calcular next_cursor
        next_cursor = estudiantes_deudores[-1].id if estudiantes_deudores and has_more else None
        
        # Construir lista de deudores
        usuarios_pendientes = []
        for estudiante in estudiantes_deudores:
            # Obtener última carrera
            ultima_carrera = None
            
            ultimo_pago = (
                session.query(Payment)
                .filter(Payment.user_id == estudiante.id)
                .order_by(Payment.affected_month.desc())
                .first()
            )
            
            if ultimo_pago and ultimo_pago.carer:
                ultima_carrera = ultimo_pago.carer.name
            elif estudiante.userdetail.carer:
                ultima_carrera = estudiante.userdetail.carer.name
            else:
                ultima_carrera = "Sin carrera asignada"
            
            # Contar pagos realizados
            total_pagos = (
                session.query(Payment)
                .filter(Payment.user_id == estudiante.id)
                .count()
            )
            
            usuarios_pendientes.append({
                "id": estudiante.id,
                "username": estudiante.username,
                "firstName": estudiante.userdetail.firstName,
                "lastName": estudiante.userdetail.lastName,
                "fullname": f"{estudiante.userdetail.firstName} {estudiante.userdetail.lastName}",
                "email": estudiante.userdetail.email,
                "dni": estudiante.userdetail.dni,
                "carer": ultima_carrera,
                "carer_id": estudiante.userdetail.carer_id,
                "total_pagos_realizados": total_pagos
            })
        
        # Contar total de deudores (solo en primera carga)
        total_count = None
        if last_seen_id is None:
            todos_estudiantes = (
                session.query(User)
                .join(UserDetails)
                .filter(UserDetails.type == "estudiante")
                .all()
            )
            total_count = len([est for est in todos_estudiantes if est.id not in usuarios_con_pago])
        
        return {
            "count": total_count,
            "month": mes_actual,
            "year": anio_actual,
            "deudores": usuarios_pendientes,
            "next_cursor": next_cursor
        }
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": "Error interno"})
    finally:
        session.close()


@payment.get("/payment/pending/search")
def search_deudores(
    q: str,
    limit: int = 50,
    req: Request = None
):
    try:
        # Verificar token (opcional, dependiendo de tu seguridad)
        # has_access = Security.verify_token(req.headers)
        # if "iat" not in has_access:
        #     return JSONResponse(status_code=401, content=has_access)

        from datetime import datetime
        mes_actual = datetime.now().month
        anio_actual = datetime.now().year
        
        # Obtener pagos del mes actual
        pagos_mes = (
            session.query(Payment.user_id)
            .filter(
                extract('month', Payment.affected_month) == mes_actual,
                extract('year', Payment.affected_month) == anio_actual
            )
            .distinct()
            .all()
        )
        
        # Set de usuarios que ya pagaron
        usuarios_con_pago = {pago.user_id for pago in pagos_mes}
        
        # Query de estudiantes con filtro de búsqueda
        q_like = f"%{q}%"
        estudiantes_query = (
            session.query(User)
            .options(
                joinedload(User.userdetail).joinedload(UserDetails.carer)
            )
            .join(UserDetails)
            .filter(UserDetails.type == "estudiante")
            .filter(
                (User.username.ilike(q_like)) |
                (UserDetails.firstName.ilike(q_like)) |
                (UserDetails.lastName.ilike(q_like)) |
                (UserDetails.email.ilike(q_like)) |
                (UserDetails.dni.cast(String).ilike(q_like))
            )
            .order_by(User.id.asc())
            .limit(limit)
            .all()
        )
        
        # Filtrar solo los deudores
        estudiantes_deudores = [
            est for est in estudiantes_query
            if est.id not in usuarios_con_pago and est.userdetail
        ]
        
        # Construir lista de deudores
        usuarios_pendientes = []
        for estudiante in estudiantes_deudores:
            # Obtener última carrera
            ultima_carrera = None
            
            ultimo_pago = (
                session.query(Payment)
                .filter(Payment.user_id == estudiante.id)
                .order_by(Payment.affected_month.desc())
                .first()
            )
            
            if ultimo_pago and ultimo_pago.carer:
                ultima_carrera = ultimo_pago.carer.name
            elif estudiante.userdetail.carer:
                ultima_carrera = estudiante.userdetail.carer.name
            else:
                ultima_carrera = "Sin carrera asignada"
            
            # Contar pagos realizados
            total_pagos = (
                session.query(Payment)
                .filter(Payment.user_id == estudiante.id)
                .count()
            )
            
            usuarios_pendientes.append({
                "id": estudiante.id,
                "username": estudiante.username,
                "firstName": estudiante.userdetail.firstName,
                "lastName": estudiante.userdetail.lastName,
                "fullname": f"{estudiante.userdetail.firstName} {estudiante.userdetail.lastName}",
                "email": estudiante.userdetail.email,
                "dni": estudiante.userdetail.dni,
                "carer": ultima_carrera,
                "carer_id": estudiante.userdetail.carer_id,
                "total_pagos_realizados": total_pagos
            })
        
        return {
            "deudores": usuarios_pendientes,
            "count": len(usuarios_pendientes),
            "month": mes_actual,
            "year": anio_actual
        }
        
    except Exception as e:
        print("Error buscando deudores:", e)
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"detail": "Error interno"})
    finally:
        session.close()

class InputPaginatedRequest(BaseModel):
    limit: int = 10
    last_seen_id: Optional[int] = None
    user_id: Optional[int] = None
    start_date: Optional[datetime] = None 
    end_date: Optional[datetime] = None 