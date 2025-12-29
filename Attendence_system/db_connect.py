import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        # 1. Password check
        password = os.environ.get("MYSQL_ROOT_PASSWORD") or os.environ.get("MYSQLPASSWORD") or os.environ.get("MYSQL_PASSWORD")
        
        # 2. Host check
        host = os.environ.get("MYSQLHOST") or "ballast.proxy.rlwy.net"
        
        # 3. Port handle
        p = os.environ.get("MYSQLPORT")
        port = int(p) if p else 50532

        # 4. Database Name
        db_name = os.environ.get("MYSQL_DATABASE") or os.environ.get("MYSQLDATABASE") or "railway"

        # Connection setup
        connection = mysql.connector.connect(
            host=host,
            user=os.environ.get("MYSQLUSER") or "root",
            password=password,
            database=db_name,
            port=port
        )

        if connection.is_connected():
            return connection

    except Error as e:
        print(f"Connection Error Detail: {e}")
        return None
