from fastapi import APIRouter, HTTPException, Request, Query
from models.modelo import AsyncSessionLocal, InputPaginatedRequestFilter, session, User, InputUser, InputLogin, UserDetails, InputPaginatedRequest
from sqlalchemy.orm import joinedload
from fastapi.responses import JSONResponse
from psycopg2 import IntegrityError
from auth.security import Security
from typing import Optional
from sqlalchemy import or_, select

user = APIRouter()


@user.get("/")
def helloUser():
    return "Hello user!!"


@user.post("/users/new")
def crear_usuario(user: InputUser):
    try:
        # Verifica si el username ya existe
        if not validate_user(user.username):
            return JSONResponse(
                status_code=400, content={"detail": "El usuario ya existe"}
            )

        # Verifica si el email ya existe
        if not validate_email(user.email):
            return JSONResponse(
                status_code=400, content={"detail": "El email ya existe"}
            )

        # Verifica si el DNI ya existe
        dni_existente = session.query(UserDetails).filter_by(dni=user.dni).first()
        if dni_existente:
            return JSONResponse(
                status_code=400, content={"detail": "El DNI ya está registrado"}
            )

        # Crear usuario
        newUser = User(user.username, user.password)
        newUserDetail = UserDetails(
            dni=user.dni,
            firstName=user.firstName,
            lastName=user.lastName,
            type=user.type,
            email=user.email,
            carer_id=user.carer_id,
        )
        newUser.userdetail = newUserDetail

        session.add(newUser)
        session.commit()

        return JSONResponse(
            status_code=200, content={"detail": "Usuario agregado correctamente"}
        )

    except IntegrityError as e:
        session.rollback()
        if "username" in str(e.orig):
            return JSONResponse(
                status_code=400, content={"detail": "El nombre de usuario ya existe"}
            )
        elif "email" in str(e.orig):
            return JSONResponse(
                status_code=400, content={"detail": "El email ya está en uso"}
            )
        elif "dni" in str(e.orig):
            return JSONResponse(
                status_code=400, content={"detail": "El DNI ya está en uso"}
            )
        else:
            print("Error de integridad inesperado:", e)
            return JSONResponse(
                status_code=500, content={"detail": "Error de base de datos"}
            )

    except Exception as e:
        session.rollback()
        print("Error inesperado:", e)
        return JSONResponse(
            status_code=500, content={"detail": "Error interno del servidor"}
        )

    finally:
        session.close()


@user.post("/users/loginUser")
def login_post(usu: InputLogin):
    try:
        res = (
            session.query(User)
            .options(joinedload(User.userdetail))
            .filter(User.username == usu.username)
            .first()
        )

        if not res:
            return {"status": "error", "message": "Usuario no encontrado"}

        if res.password != usu.password:
            return {"status": "error", "message": "Contraseña incorrecta"}

        token = Security.generate_token(res)

        if not token:
            return {"status": "error", "message": "Error en la generación del token"}

        user_data = {
            "id": res.id,
            "username": res.username,
            "email": res.userdetail.email,
            "dni": res.userdetail.dni,
            "firstName": res.userdetail.firstName,
            "lastName": res.userdetail.lastName,
            "type": res.userdetail.type,
            "carer_id": res.userdetail.carer_id,
        }

        return {
            "status": "success",
            "token": token,
            "user": user_data,
            "message": "Accedido",
        }

    except Exception as e:
        print("Error en login:", e)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "Error interno del servidor"},
        )


@user.get("/users/alls")
def obtener_usuario_detalle():
    try:
        usuarios = session.query(User).options(joinedload(User.userdetail)).all()
        usuarios_con_detalles = []
        for usuario in usuarios:
            usuario_con_detalle = {
                "id": usuario.id,
                "username": usuario.username,
                "email": usuario.userdetail.email,
                "dni": usuario.userdetail.dni,
                "firstName": usuario.userdetail.firstName,
                "lastName": usuario.userdetail.lastName,
                "type": usuario.userdetail.type,
            }
            usuarios_con_detalles.append(usuario_con_detalle)

        return JSONResponse(status_code=200, content=usuarios_con_detalles)
    except Exception as e:
        print("Error al obtener usuarios:", e)
        return JSONResponse(
            status_code=500, content={"detail": "Error al obtener usuarios"}
        )


@user.get("/users/available/{id}")
def obtener_usuarios_para_mensajes(id: int):
    usuario = session.query(User).filter(User.id == id).first()
    if not usuario or not usuario.userdetail:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    tipo = usuario.userdetail.type

    if tipo == "profesor":
        usuarios = (
            session.query(User)
            .join(User.userdetail)
            .filter(UserDetails.type == "estudiante")
            .all()
        )

    elif tipo == "estudiante":
        usuarios = (
            session.query(User)
            .join(User.userdetail)
            .filter(UserDetails.type == "profesor")
            .all()
        )
    else:
        usuarios = []

    return [
        {
            "id": u.id,
            "nombre": f"{u.userdetail.firstName} {u.userdetail.lastName}",
        }
        for u in usuarios
    ]


@user.put("/users/{user_id}")
def update_user_password(user_id: int, data: dict):
    usuario = session.query(User).filter(User.id == user_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    usuario.password = data.get("password")
    session.commit()
    return {"message": "Contraseña actualizada"}


@user.get("/users/profesores/all")
def get_profesores():
    try:
        # session = SessionLocal()  # Si usás SQLAlchemy puro
        profesores = (
            session.query(User)
            .join(UserDetails, User.id_userdetail == UserDetails.id)
            .filter(UserDetails.type == "profesor")
            .all()
        )
        return [{"id": prof.id, "username": prof.username} for prof in profesores]
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        session.close()


def validate_user(username: str) -> bool:
    return session.query(User).filter_by(username=username).first() is None


def validate_email(email: str) -> bool:
    return session.query(UserDetails).filter_by(email=email).first() is None


@user.get("/users/paginated-by-type")
def getUsersPaginatedByType(
    req: Request, 
    user_type: str = Query(..., regex="^(profesor|estudiante)$"),
    limit: int = Query(20, gt=0, le=100), 
    offset: int = Query(0, ge=0)
):
    try:
        has_access = Security.verify_token(req.headers)
        if "iat" in has_access:
            query = (
                session.query(User)
                .options(joinedload(User.userdetail))
                .filter(User.userdetail.has(type=user_type))
                .order_by(User.id)
            )

            total_users = query.count()
            usersWithDetail = query.offset(offset).limit(limit).all()

            usuarios_con_detalle = []
            for usuario in usersWithDetail:
                usuarios_con_detalle.append(
                    {
                        "id": usuario.id,
                        "username": usuario.username,
                        "email": usuario.userdetail.email,
                        "dni": usuario.userdetail.dni,
                        "firstName": usuario.userdetail.firstName,
                        "lastName": usuario.userdetail.lastName,
                        "type": usuario.userdetail.type,
                    }
                )

            return JSONResponse(
                status_code=200,
                content={
                    "users": usuarios_con_detalle, 
                    "total": total_users,
                    "type": user_type
                },
            )
        else:
            return JSONResponse(status_code=401, content=has_access)
    except Exception as ex:
        print(f"Error al obtener página de usuarios tipo {user_type}---->> ", ex)
        return {"message": f"Error al obtener página de usuarios tipo {user_type}"}
    

@user.post("/users/paginated")
async def get_users_paginated(
    req: Request,
    body: InputPaginatedRequest
):
    try:
        has_access = Security.verify_token(req.headers)
        if "iat" not in has_access:
            return JSONResponse(status_code=401,
            content=has_access)

        limit = body.limit
        last_seen_id = body.last_seen_id

        query = (
            session.query(User).options(joinedload(User.
            userdetail)).order_by(User.id)
        ) 
        if last_seen_id is not None:
            query = query.filter(User.id>last_seen_id) 

        user_with_detail = query.limit(limit)

        usuarios_con_detalles = []
        for us in user_with_detail:
            user_con_detalle = {
                "id": us.id,
                "username": us.username,
                "email": us.userdetail.email,
                "dni": us.userdetail.dni,
                "firstName": us.userdetail.firstName,
                "lastName": us.userdetail.lastName,
                "type": us.userdetail.type,
            }
            usuarios_con_detalles.append(user_con_detalle)

        next_cursor = (
            usuarios_con_detalles[-1]["id"]
            if len(usuarios_con_detalles)== limit else None
        )

        return JSONResponse(
            status_code=200,
            content = {"users":usuarios_con_detalles, "next_cursor":next_cursor}
        ) 
    
    except Exception as ex: 
        print ("Error al obtener pagina de usuarios ---> ", ex)
        return JSONResponse(
            status_code=500,
            content={"message": "Error al obtener pagina de usuarios"}
        )    



@user.get("/users/search-by-type")
def search_users_by_type(
    req: Request,
    user_type: str = Query(..., regex="^(profesor|estudiante)$"),
    q: Optional[str] = Query(None),
    limit: int = Query(20, gt=0, le=100),
    offset: int = Query(0, ge=0)
):
    try:
        has_access = Security.verify_token(req.headers)
        if "iat" not in has_access:
            return JSONResponse(status_code=401, content=has_access)

        query = (
            session.query(User)
            .options(joinedload(User.userdetail))
            .filter(User.userdetail.has(type=user_type))
        )

        if q:
            search_filter = f"%{q.lower()}%"
            query = query.filter(
                (User.userdetail.has(UserDetails.firstName.ilike(search_filter))) |
                (User.userdetail.has(UserDetails.lastName.ilike(search_filter)))
            )

        total = query.count()
        users = query.order_by(User.id).offset(offset).limit(limit).all()

        usuarios_con_detalle = []
        for usuario in users:
            usuarios_con_detalle.append(
                {
                    "id": usuario.id,
                    "username": usuario.username,
                    "email": usuario.userdetail.email,
                    "dni": usuario.userdetail.dni,
                    "firstName": usuario.userdetail.firstName,
                    "lastName": usuario.userdetail.lastName,
                    "type": usuario.userdetail.type,
                }
            )

        return JSONResponse(
            status_code=200,
            content={
                "users": usuarios_con_detalle,
                "total": total,
                "type": user_type,
            },
        )
    except Exception as ex:
        print(f"Error al buscar usuarios tipo {user_type}: ", ex)
        return JSONResponse(
            status_code=500,
            content={"message": "Error al buscar usuarios"},
        )

# ***********lo hicimos con el profe*************
@user.post("/users/paginated/filtered-dict-sync")
def get_users_paginated_filtered_syng(req: Request, body: InputPaginatedRequest):
    try:
        has_access = Security.verify_token(req.headers)
        if "iat" not in has_access:
            return JSONResponse(status_code=401, content=has_access)
        limit = body.limit
        last_seen_id = body.last_seen_id
        search_text = getattr(body, "search","").strip()
        query = (
            session.query(User)
            .join(User.userdetail)
            .options(joinedload(User.userdetail))
            .order_by(User.id)
        )

        if last_seen_id is not None:
            query = query.filter(User.id > last_seen_id)

        if search_text:
            search_pattern = f"%{search_text}%"
            query = query.filter(
                or_(
                    UserDetails.firstName.ilike(search_pattern),
                    UserDetails.lastName.ilike(search_pattern),
                    UserDetails.email.ilike(search_pattern),
                )
            )

        query = query.limit(limit)

        users_with_detail = query.all()

        usuarios_con_detalle = []

        for us in users_with_detail:
            usuario_con_detalle = {
                "id": us.id,
                "username": us.username,
                "first_name": us.userdetail.firstName,
                "last_name": us.userdetail.lastName,
                "dni": us.userdetail.dni,
                "type": us.userdetail.type,
                "email": us.userdetail.email
            }
            usuarios_con_detalle.append(usuario_con_detalle)

        next_cursor = (
            usuarios_con_detalle[-1]["id"]
            if len(usuarios_con_detalle) == limit
            else None
        )

        return JSONResponse(
            status_code=200,
            content={
                "users": usuarios_con_detalle,
                "next_cuerso": next_cursor
            }
        )
    
    except Exception as error:
        print("Error al optener pagina filtada de usuarios --> ", error)
        return JSONResponse(
            status_code=500,
            content= {
                "message":"Error al optener pagina de filtrado"
            }
        )

@user.post("/users/paginated/filtered-async")
async def get_users_paginated_filtered_async(
    req: Request, body: InputPaginatedRequestFilter
):
    try:
        has_access = Security.verify_token[req.headers]
        if "iat" not in has_access:
            return JSONResponse(status_code=401, content=has_access)
        
        limit = body.limit
        last_seen_id = body.last_seen_id

        async with AsyncSessionLocal() as session:
            #construimos la colsulta
            stmt = (select(User).join(User.userdetail).options(joinedload(User.userdetail)).order_by(User.id))

            #Filtros agregados a la consulta 
            if hasattr(body, "filters") and body.filters:
                if "username" in body.filters:
                    str_buscado = f"%{body.filters["username"]}%"
                    stmt = stmt.filter(User.username.ilike(str_buscado)) 
            
                if "type" in body.filters:
                    stmt = stmt.filter(UserDetails.type == body.filters["type"]) 

                if "email" in body.filters:
                    str_buscado = f"%{body.filters["email"]}%"
                    stmt = stmt.filter(UserDetails.email.ilike(str_buscado)) 
            
            #Agrego filtro del cursor a la consulta
            if last_seen_id is not None:
                stmt = stmt.filter(User.id > last_seen_id) 

            #Agregar limit
            stmt = stmt.limit(limit) 

            #Ejecuto consulta
            result = await session.execute(stmt)
            users_with_detail = result.scalars().all()

            #Armo la salida de datos para el front
            usuarios_con_detalles = [
                {
                    "id": us.id,
                    "username": us.username,
                    "email": us.userdetail.email,
                    "dni": us.userdetail.dni,
                    "firstName": us.userdetail.firstName,
                    "lastName": us.userdetail.lastName,
                    "type": us.userdetail.type,
                }
                for us in users_with_detail
            ]  

            # if len(usuarios_con_detalles) == limit:
            #     next_cursor = usuarios_con_detalles[-1]["id"]
            # else:
            #     next_cursor = None

            next_cursor = (
                usuarios_con_detalles[-1]["id"]
                if len(usuarios_con_detalles) == limit
                else None
            ) 

            return JSONResponse (
                status_code=200,
                content={
                    "users": usuarios_con_detalles,
                    "next_cursor": next_cursor
                }
            )        
    
    except Exception as error:
        print("Error al obtener pagina de usuarios", error)
        return JSONResponse(
            status_code=500,
            countent={
                "message":"Error al obtener pagina de usuarios"
            }
        )
                
