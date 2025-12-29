import os
import mysql.connector

def get_connection():
    port_env = os.environ.get("MYSQLPORT")

    port_to_use = int(port_env) if port_env else 50532

    return mysql.connector.connect(
        host = os.environ.get("MYSQLHOST"),
        user = os.environ.get("MYSQLUSER"),
        password = os.environ.get("MYSQLPASSWORD"),
        database = os.environ.get("MYSQLDATABASE") or os.environ.get("MYSQLDATABASE"),
        port = port_to_use
    )
    











