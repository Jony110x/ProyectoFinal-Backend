from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine("postgresql://proyectofinal_l186_user:VACfvZBCDASb4E0ffJUK6ecjrL1x8ldc@dpg-d3tcakn5r7bs73emq7fg-a/proyectofinal_l186")
# engine = create_engine("postgresql://postgres:1234@localhost:5432/proyectoFinal-copia")

Base = declarative_base()