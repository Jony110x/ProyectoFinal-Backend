from fastapi import APIRouter, Form, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from models.modelo import session, Message, User
from models.modelo import (
    UserDetails,
    alumno_materia,
    Payment,
    profesor_materia,
)
import datetime
import os
import cloudinary
import cloudinary.uploader
from cloudinary.utils import cloudinary_url

# Configuración 
cloudinary.config(
    cloud_name="dydhfghau",
    api_key="231924475335554",
    api_secret="ZytmRYQuMFnRJHEGDYFjN17QTro",
    secure=True
)

message = APIRouter()

BASE_URL = "http://localhost:8000"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ENDPOINT ÚNICO PARA ENVIAR MENSAJES (con o sin archivo)
@message.post("/messages/send")
async def send_message(
    sender_id: int = Form(...),
    receiver_id: int = Form(...),
    content: str = Form(""),
    file: UploadFile = File(None)
):
    try:
        # Validar que haya contenido o archivo
        if not content.strip() and not file:
            raise HTTPException(
                status_code=422, 
                detail="Debe proporcionar contenido del mensaje o un archivo"
            )
        
        # Verificar que los usuarios existan
        sender = session.query(User).get(sender_id)
        receiver = session.query(User).get(receiver_id)
        
        if not sender or not receiver:
            raise HTTPException(
                status_code=404, 
                detail="Usuario no encontrado"
            )

        # Manejar archivo adjunto con Cloudinary
        archivo_url = None
        if file and file.filename:
            try:
                # Determinar el tipo de recurso según la extensión
                file_extension = file.filename.split('.')[-1].lower()
                
                # Para PDFs y documentos usar 'raw', para imágenes 'image', para videos 'video'
                if file_extension in ['pdf', 'doc', 'docx', 'txt', 'xls', 'xlsx', 'zip', 'rar']:
                    resource_type = "raw"
                elif file_extension in ['mp4', 'avi', 'mov', 'mkv']:
                    resource_type = "video"
                else:
                    resource_type = "auto"
                
                # Subir archivo a Cloudinary
                result = cloudinary.uploader.upload(
                    file.file,
                    folder="mensajes_adjuntos",
                    resource_type=resource_type,
                    public_id=f"{int(datetime.datetime.now().timestamp())}_{file.filename.rsplit('.', 1)[0]}",
                    format=file_extension if resource_type == "raw" else None
                )
                
                # Obtener la URL segura del archivo
                archivo_url = result.get("secure_url")
                
            except Exception as e:
                print(f"Error subiendo archivo a Cloudinary: {e}")
                raise HTTPException(
                    status_code=500, 
                    detail="Error al subir el archivo"
                )

        # Crear mensaje
        nuevo = Message(
            sender_id=sender_id,
            receiver_id=receiver_id,
            content=content.strip(),
            timestamp=datetime.datetime.utcnow(),
            file_url=archivo_url
        )
        
        session.add(nuevo)
        session.commit()
        session.refresh(nuevo)
        
        return {
            "id": nuevo.id,
            "sender_id": nuevo.sender_id,
            "receiver_id": nuevo.receiver_id,
            "content": nuevo.content,
            "timestamp": nuevo.timestamp,
            "file_url": nuevo.file_url
        }
        
    except HTTPException as e:
        session.rollback()
        raise e
    except Exception as e:
        session.rollback()
        print("Error al enviar mensaje:", e)
        raise HTTPException(status_code=500, detail="Error interno al enviar mensaje")



@message.get("/messages/{user_id}")
def get_messages(user_id: int):
    try:
        mensajes = (
            session.query(Message)
            .filter((Message.sender_id == user_id) | (Message.receiver_id == user_id))
            .order_by(Message.timestamp.desc())
            .all()
        )

        resultados = []
        for msg in mensajes:
            sender = session.query(User).filter_by(id=msg.sender_id).first()
            full_name = "Usuario desconocido"
            if sender and sender.userdetail:
                full_name = f"{sender.userdetail.firstName} {sender.userdetail.lastName}"

            resultados.append(
                {
                    "id": msg.id,
                    "sender_id": msg.sender_id,
                    "receiver_id": msg.receiver_id,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "sender_name": full_name,
                    "file_url": msg.file_url  # Incluir file_url
                }
            )

        return resultados

    except Exception as e:
        print("Error al obtener mensajes:", e)
        return []


@message.get("/messages/available/{user_id}")
def get_available_users(user_id: int, search: str = ""):
    try:
        user = session.query(User).get(user_id)
        if not user:
            return JSONResponse(
                status_code=404, content={"detail": "Usuario no encontrado"}
            )

        tipo = user.userdetail.type.lower()

        if tipo == "admin":
            usuarios = session.query(User).filter(User.id != user_id)
        elif tipo == "profesor":
            usuarios = (
                session.query(User)
                .join(UserDetails)
                .filter(User.id != user_id)
                .filter(UserDetails.type.in_(["admin", "estudiante"]))
            )
        elif tipo == "estudiante":
            usuarios = (
                session.query(User)
                .join(UserDetails)
                .filter(User.id != user_id)
                .filter(UserDetails.type.in_(["admin", "profesor"]))
            )
        else:
            return JSONResponse(
                status_code=400, content={"detail": "Tipo de usuario desconocido"}
            )

        # Filtrado por nombre si hay término de búsqueda
        if search and len(search.strip()) >= 2:  # Solo buscar con al menos 2 caracteres
            usuarios = usuarios.join(UserDetails).filter(
                (UserDetails.firstName + " " + UserDetails.lastName).ilike(
                    f"%{search.strip()}%"
                )
            )
            # Aumentar límite cuando hay búsqueda activa
            usuarios = usuarios.limit(50).all()
        else:
            # Sin búsqueda, mostrar solo los primeros 20
            usuarios = usuarios.limit(20).all()

        resultado = []
        for u in usuarios:
            nombre = "Usuario desconocido"
            if u.userdetail:
                nombre = f"{u.userdetail.firstName} {u.userdetail.lastName}"
            resultado.append({
                "id": u.id, 
                "nombre": nombre, 
                "type": u.userdetail.type if u.userdetail else "unknown"
            })

        return resultado

    except Exception as e:
        print("Error al obtener usuarios disponibles:", e)
        return JSONResponse(status_code=500, content={"detail": "Error interno"})


@message.get("/notifications/{user_id}/{user_type}")
def get_notifications(user_id: int, user_type: str):
    try:
        notifs = []

        # Mensajes (todos los usuarios)
        mensaje = (
            session.query(Message)
            .filter(Message.receiver_id == user_id)
            .order_by(Message.timestamp.desc())
            .first()
        )
        if mensaje:
            sender = session.query(User).filter_by(id=mensaje.sender_id).first()
            nombre = "Usuario desconocido"
            if sender and sender.userdetail:
                nombre = f"{sender.userdetail.firstName} {sender.userdetail.lastName}"

            notifs.append(
                {
                    "tipo": "mensaje",
                    "texto": f"Mensaje de {nombre}: {mensaje.content[:40]}...",
                    "fecha": mensaje.timestamp,
                }
            )

        # Si es profesor: asignaciones
        if user_type == "profesor":
            asignaciones = (
                session.query(profesor_materia)
                .filter(profesor_materia.c.user_id == user_id)
                .all()
            )

            if asignaciones:
                cantidad = len(asignaciones)
                notifs.append(
                    {
                        "tipo": "asignacion",
                        "texto": f"Se te ha asignado a {cantidad} materia(s).",
                        "fecha": datetime.datetime.now(),
                    }
                )

        # Si es estudiante: notas y pagos
        if user_type == "estudiante":
            # Notas
            notas = (
                session.query(alumno_materia)
                .filter(
                    alumno_materia.c.user_id == user_id, 
                    alumno_materia.c.nota != None
                )
                .all()
            )

            if notas:
                notifs.append(
                    {
                        "tipo": "nota",
                        "texto": f"Se han cargado {len(notas)} nota(s).",
                        "fecha": datetime.datetime.now(),
                    }
                )

            # Pagos
            pagos = (
                session.query(Payment)
                .filter(Payment.user_id == user_id)
                .order_by(Payment.created_at.desc())
                .all()
            )

            if pagos:
                pago = pagos[0]  # último
                notifs.append(
                    {
                        "tipo": "pago",
                        "texto": f"Se registró un pago de ${pago.amount} para {pago.affected_month.strftime('%B %Y')}.",
                        "fecha": pago.created_at,
                    }
                )
        
        leidas = notificaciones_leidas.get(user_id, [])
        notifs_filtradas = [n for n in notifs if n["texto"] not in leidas]

        return notifs_filtradas

    except Exception as e:
        print("Error en get_notifications:", e)
        return []


notificaciones_leidas = {}  # { user_id: [texto1, texto2, ...] }


class NotificacionLeidaInput(BaseModel):
    user_id: int
    texto: str


@message.post("/notifications/marcar-leida")
def marcar_notificacion_leida(data: NotificacionLeidaInput):
    user_id = data.user_id
    texto = data.texto

    if user_id not in notificaciones_leidas:
        notificaciones_leidas[user_id] = []

    if texto not in notificaciones_leidas[user_id]:
        notificaciones_leidas[user_id].append(texto)

    return {"status": "ok", "mensaje": "Notificación marcada como leída"}


class NotificacionTipoInput(BaseModel):
    user_id: int
    tipo: str  # "mensaje", "nota", "pago", "asignacion"


@message.post("/notifications/marcar-tipo-leido")
def marcar_notificaciones_tipo(data: NotificacionTipoInput):
    user_id = data.user_id
    tipo = data.tipo

    if user_id not in notificaciones_leidas:
        notificaciones_leidas[user_id] = []

    # Recalcular las notificaciones actuales
    notifs = get_notifications(user_id, tipo_usuario(user_id))
    for n in notifs:
        if n["tipo"] == tipo and n["texto"] not in notificaciones_leidas[user_id]:
            notificaciones_leidas[user_id].append(n["texto"])

    return {
        "status": "ok",
        "mensaje": f"Notificaciones tipo '{tipo}' marcadas como leídas",
    }


def tipo_usuario(user_id: int) -> str:
    user = session.query(User).filter(User.id == user_id).first()
    if user and user.userdetail:
        return user.userdetail.type
    return "estudiante"  # fallback


# Eliminar mensaje individual
@message.delete("/messages/{msg_id}")
def delete_message(msg_id: int):
    try:
        msg = session.query(Message).get(msg_id)
        if not msg:
            raise HTTPException(status_code=404, detail="Mensaje no encontrado")

        ahora = datetime.datetime.utcnow()
        if (ahora - msg.timestamp).total_seconds() > 600:  # 10 minutos
            raise HTTPException(
                status_code=403,
                detail="Solo se pueden eliminar mensajes de los últimos 10 minutos",
            )

        # Borrar archivo si existe
        if msg.file_url:
            # Extraer el path del archivo desde la URL
            filename = msg.file_url.split('/')[-1]  # Obtener solo el nombre del archivo
            filepath = os.path.join(UPLOAD_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)

        session.delete(msg)
        session.commit()
        return {"status": "ok", "mensaje": "Mensaje eliminado"}
        
    except HTTPException as e:
        raise e
    except Exception as e:
        session.rollback()
        print("Error eliminando mensaje:", e)
        raise HTTPException(status_code=500, detail="Error interno")


# Eliminar chat completo
@message.delete("/messages/chat/{user_id}/{otro_user_id}")
def delete_chat(user_id: int, otro_user_id: int):
    try:
        mensajes = (
            session.query(Message)
            .filter(
                ((Message.sender_id == user_id) & (Message.receiver_id == otro_user_id))
                | (
                    (Message.sender_id == otro_user_id)
                    & (Message.receiver_id == user_id)
                )
            )
            .all()
        )

        for msg in mensajes:
            if msg.file_url:
                # Extraer el path del archivo desde la URL
                filename = msg.file_url.split('/')[-1]
                filepath = os.path.join(UPLOAD_DIR, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
            session.delete(msg)

        session.commit()
        return {"status": "ok", "mensaje": "Chat eliminado"}
        
    except Exception as e:
        session.rollback()
        print("Error eliminando chat:", e)
        raise HTTPException(status_code=500, detail="Error interno")