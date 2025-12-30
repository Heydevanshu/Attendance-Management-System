import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        host = os.environ.get("MYSQLHOST") or "mysql.railway.internal"
        user = os.environ.get("MYSQLUSER") or "root"
        
        password = os.environ.get("MYSQL_ROOT_PASSWORD") or "IyzPAnsHRQJWxmaWKHyHAZzlUnjAJEpl"
        
        database = os.environ.get("MYSQL_DATABASE") or "railway"

        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=3306,
            auth_plugin='caching_sha2_password'
        )
        
        if connection.is_connected():
            return connection

    except Error as e:
        print(f"Detailed Connection Error: {e}")
        return None
