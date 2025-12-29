import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        host = os.environ.get("MYSQLHOST") or "ballast.proxy.rlwy.net"
        user = os.environ.get("MYSQLUSER") or "root"
        
        # Password 
        password = os.environ.get("MYSQL_ROOT_PASSWORD") or os.environ.get("MYSQLPASSWORD")
        
        # Port handle 
        p = os.environ.get("MYSQLPORT")
        port = int(p) if p else 50532
        
        database = os.environ.get("MYSQL_DATABASE") or os.environ.get("MYSQLDATABASE") or "railway"

        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port
        )
        return connection

    except Error as e:
        print(f"Connection Error Detail: {e}")
        return None
