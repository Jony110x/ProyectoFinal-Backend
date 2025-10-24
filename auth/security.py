import datetime, pytz, jwt

class Security:
    secret = "cualquier cosa"

    @classmethod
    def hoy(cls):
        return datetime.datetime.now(pytz.timezone("America/Buenos_Aires"))

    @classmethod
    def generate_token(cls, authUser):   
        ahora = cls.hoy()     
        payload = {
            "iat": int(ahora.timestamp()),
            "exp": int((ahora + datetime.timedelta(minutes=480)).timestamp()),
            "username": authUser.username
        }
        try:
            return jwt.encode(payload, cls.secret, algorithm="HS256")
        except Exception as e:
            print("Error en JWT: ", e)
            return None


    @classmethod
    def verify_token(cls, headers):
        """Decodifica el JWT recibido en el header Authorization."""
        token_header = headers.get("authorization")
        if not token_header:
            return {"error": "No authorization header"}

        try:
            # Quitar el "Bearer " del inicio
            token = token_header.split(" ")[1]
            payload = jwt.decode(token, cls.secret, algorithms=["HS256"])
            return payload
        except Exception as e:
            print("Error al verificar token: ", e)
            return {"error": "Token inválido o expirado"}
