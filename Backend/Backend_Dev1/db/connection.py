import os
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Cargar variables de entorno desde .env (busca en directorio actual, módulo y raíz)
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, ".env"))
load_dotenv(os.path.join(os.path.dirname(base_dir), ".env"))
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("db_connection")

# URL por defecto a Tiger Data (Timescale Cloud) si no existe archivo .env local
DEFAULT_TIGER_URL = "postgres://tsdbadmin:q33z9gicarant7kc@tsfgwbki2d.w84nx9piyi.tsdb.cloud.timescale.com:39869/tsdb?sslmode=require"

# Parámetros de conexión a Tiger Data (PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("TIGER_DATA_URL") or DEFAULT_TIGER_URL
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "courier_db")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_SSLMODE = os.getenv("DB_SSLMODE", "prefer")


def get_db_connection():
    """
    Retorna una conexión activa a la base de datos PostgreSQL / Tiger Data.
    Soporta tanto DATABASE_URL (URL completa) como variables individuales.
    """
    try:
        if DATABASE_URL:
            conn = psycopg2.connect(DATABASE_URL)
        else:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                dbname=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD,
                sslmode=DB_SSLMODE
            )
        return conn
    except Exception as e:
        logger.error(f"Error al conectar con la base de datos: {e}")
        raise e


def init_db(schema_path: str = None):
    """
    Ejecuta el archivo schema.sql para inicializar las tablas requeridas.
    """
    if schema_path is None:
        base_dir = os.path.dirname(__file__)
        schema_path = os.path.join(base_dir, "schema.sql")

    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"No se encontró el archivo de esquema en: {schema_path}")

    with open(schema_path, "r", encoding="utf-8") as f:
        sql_script = f.read()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql_script)
        conn.commit()
        logger.info("Esquema de Tiger Data inicializado exitosamente (orders, driver_logs, transactions).")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error ejecutando el script de inicialización: {e}")
        raise e
    finally:
        conn.close()


if __name__ == "__main__":
    print("=== Probando conexión e inicialización de Tiger Data ===")
    try:
        init_db()
        print("¡Conexión y tablas verificadas con éxito!")
    except Exception as err:
        print(f"Nota: Configura tus credenciales en el archivo .env ({err})")
