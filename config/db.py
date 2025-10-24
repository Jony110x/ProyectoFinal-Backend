from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine("postgresql://proyectofinal_l186_user:VACfvZBCDASb4E0ffJUK6ecjrL1x8ldc@dpg-d3tcakn5r7bs73emq7fg-a/proyectofinal_l186")

Base = declarative_base()