import os
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host = os.environ.get("MYSQLHOST"),
        user = os.environ.get("MYSQLUSER"),
        password = os.environ.get("MYSQLPASSWORD"),
        database = os.environ.get("MYSQLDATABASE"),
        port = int(os.enviorn.get("MYSQLPORT"))
    )
