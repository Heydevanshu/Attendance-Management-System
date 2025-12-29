import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        # 1. Host
        host = os.environ.get("MYSQLHOST") or "ballast.proxy.rlwy.net"
        
        # 2. Port
        port_env = os.environ.get("MYSQLPORT")
        port = int(port_env) if port_env else 50532

        # 3. Password
        password = os.environ.get("MYSQL_ROOT_PASSWORD") or os.environ.get("MYSQLPASSWORD")

        connection = mysql.connector.connect(
            host=host,
            user=os.environ.get("MYSQLUSER") or "root",
            password=password,
            database=os.environ.get("MYSQL_DATABASE") or "railway",
            port=port
        )
        return connection

    except Error as e:
        print(f"Detailed Connection Error: {e}")
        return None
