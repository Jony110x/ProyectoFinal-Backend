import mercadopago
from fastapi import APIRouter

router = APIRouter()

sdk = mercadopago.SDK("APP_USR-1796321676137067-111511-86a35099d82e33be87aacc2e98ae3aa9-2992706176")

@router.post("/crear-pago")
def crear_pago():
    preference_data = {
        "items": [
            {
                "title": "Pago de cuota",
                "quantity": 1,
                "unit_price": 45000.0
            }
        ],
      
        "back_urls": {
            "success": "http://localhost:5173/success",
            "failure": "http://localhost:5173/failure",
            "pending": "http://localhost:5173/pending"
        },
    }

    preference = sdk.preference().create(preference_data)

    return {
        "init_point": preference["response"].get("init_point"),
        "sandbox_init_point": preference["response"].get("sandbox_init_point")
    }
