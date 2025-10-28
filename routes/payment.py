from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
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
        usuarios = session.query(User).options(joinedload(User.userdetail)).all()
        pagos = session.query(Payment).all()

        from datetime import datetime
        mes_actual = datetime.now().strftime("%Y-%m")

        usuarios_con_pago = set()
        for pago in pagos:
            if pago.affected_month.strftime("%Y-%m") == mes_actual:
                usuarios_con_pago.add(pago.user_id)

        usuarios_pendientes = [
            {
                "id": u.id,
                "fullname": f"{u.userdetail.firstName} {u.userdetail.lastName}"
            }
            for u in usuarios
            if u.userdetail and u.userdetail.type == "estudiante" and u.id not in usuarios_con_pago
        ]

        return usuarios_pendientes
    except Exception as e:
        print("Error:", e)
        return JSONResponse(status_code=500, content={"detail": "Error interno"})



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


class InputPaginatedRequest(BaseModel):
    limit: int = 10
    last_seen_id: Optional[int] = None
    user_id: Optional[int] = None
    start_date: Optional[datetime] = None 
    end_date: Optional[datetime] = None 