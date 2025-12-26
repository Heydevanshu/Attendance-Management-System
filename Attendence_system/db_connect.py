import os
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host = os.environ.get("DB_HOST"),
        user = os.environ.get("DB_USER"),

        password = os.enviorn.get("DB_PASSWORD"),
        database = os.environ.get("DB_NAME"),
        port = int(os.environ.get("DB_PORT",3306))
    )
    
