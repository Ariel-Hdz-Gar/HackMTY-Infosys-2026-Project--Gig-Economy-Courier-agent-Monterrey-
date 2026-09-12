"""
CourierAI - Inspección de Base de Datos Tiger Data (Dev 1 -> Dev 2)
------------------------------------------------------------------
Este script consulta los metadatos de PostgreSQL en Tiger Data y genera
un reporte completo de tablas, columnas, tipos de datos, llaves primarias/foráneas,
vistas y conteo de registros actuales para compartir con Dev 2 y el equipo.

Uso:
  python Backend/Backend_Dev1/tools/inspect_db.py
"""

import os
import sys

# Asegurar que encuentre la conexión a la BD
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.connection import get_db_connection

def inspeccionar_bd():
    conn = get_db_connection()
    cur = conn.cursor()

    print("=" * 80)
    print(" REPORTE DE ESTRUCTURA BASE DE DATOS TIGER DATA (DEV 1 -> DEV 2)")
    print("=" * 80)

    # 1. Tablas
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)
    tablas = [r[0] for r in cur.fetchall()]

    for tabla in tablas:
        cur.execute(f"SELECT COUNT(*) FROM {tabla};")
        count = cur.fetchone()[0]
        print(f"\n TABLA: {tabla.upper()} ({count} registros)")
        print("-" * 65)
        print(f"{'Columna':<25} | {'Tipo de Dato':<20} | {'Null?':<6} | {'Default'}")
        print("-" * 65)
        
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """, (tabla,))
        
        for col, dtype, nullable, default in cur.fetchall():
            default_str = str(default) if default else ""
            if len(default_str) > 25:
                default_str = default_str[:22] + "..."
            print(f"{col:<25} | {dtype:<20} | {nullable:<6} | {default_str}")

    # 2. Vistas
    print("\n" + "=" * 80)
    print(" VISTAS (COMPATIBILIDAD DEV 2)")
    print("=" * 80)
    
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'VIEW'
        ORDER BY table_name;
    """)
    vistas = [r[0] for r in cur.fetchall()]

    for vista in vistas:
        print(f"\n VISTA: {vista.upper()}")
        print("-" * 65)
        print(f"{'Columna (Alias)':<25} | {'Tipo de Dato':<20}")
        print("-" * 65)
        
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
        """, (vista,))
        
        for col, dtype in cur.fetchall():
            print(f"{col:<25} | {dtype:<20}")

    # 3. Foreign Keys
    print("\n" + "=" * 80)
    print(" LLAVES FORANEAS (RELACIONES)")
    print("=" * 80)
    
    cur.execute("""
        SELECT
            tc.table_name, 
            kcu.column_name, 
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name 
        FROM information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public';
    """)
    fks = cur.fetchall()
    if fks:
        for orig_table, orig_col, foreign_table, foreign_col in fks:
            print(f" • {orig_table}.{orig_col} ---> {foreign_table}.{foreign_col}")
    else:
        print(" Sin Foreign Keys explicitas.")

    # 4. Muestra de v_orders para que Dev 2 vea cómo se recibe
    print("\n" + "=" * 80)
    print(" MUESTRA DE DATOS DE `v_orders` (LO QUE DEV 2 LEE)")
    print("=" * 80)
    cur.execute("SELECT * FROM v_orders LIMIT 2;")
    colnames = [desc[0] for desc in cur.description]
    rows = cur.fetchall()
    
    if rows:
        for idx, r in enumerate(rows, 1):
            print(f"\n--- Ejemplo Pedido #{idx} ---")
            for col, val in zip(colnames, r):
                print(f"  {col:<20}: {val}")
    else:
        print(" (No hay datos en orders actualmente)")

    print("\n" + "=" * 80)
    cur.close()
    conn.close()

if __name__ == "__main__":
    inspeccionar_bd()
