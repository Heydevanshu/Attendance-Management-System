import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        # 1. for variable fetching
        user = os.environ.get("MYSQLUSER") or os.environ.get("MYSQL_USER")
        password = os.environ.get("MYSQLPASSWORD") or os.environ.get("MYSQL_PASSWORD") or os.environ.get("MYSQL_ROOT_PASSWORD")
        host = os.environ.get("MYSQLHOST") or os.environ.get("MYSQL_HOST") or "ballast.proxy.rlwy.net"
        database = os.environ.get("MYSQL_DATABASE") or os.environ.get("MYSQLDATABASE")
        
        p = os.environ.get("MYSQLPORT") or os.environ.get("MYSQL_PORT")
        port = int(p) if p else 50532

        # for debuging
        if not password:
            print("Warning: Password nahi mila, variable check karein!")

        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port
        )

        if connection.is_connected():
            return connection

    except Error as e:
        print(f"Connection Error Detail: {e}")
        return None
