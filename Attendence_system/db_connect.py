import os
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host = os.environ.get("MYSQLHOST"),
        user = os.environ("MYSQLUSER"),

        password = os.environ("MYSQLPASSWORD"),
        database = os.environ("MYSQLDATABASE"),
        port = int(os.environ("MYSQLPORT"))
    )
    







