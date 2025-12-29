import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        # Railway automatically provides these if linked
        # Internal host is usually just 'mysql' or provided via MYSQLHOST
        host = os.environ.get("MYSQLHOST") 
        user = os.environ.get("MYSQLUSER") or "root"
        password = os.environ.get("MYSQL_ROOT_PASSWORD") or os.environ.get("MYSQLPASSWORD")
        database = os.environ.get("MYSQL_DATABASE") or "railway"
        
        # Internal port is 3306, Public is 50532. 
        # We try to detect which one to use.
        port_env = os.environ.get("MYSQLPORT")
        port = int(port_env) if port_env else 3306 

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
