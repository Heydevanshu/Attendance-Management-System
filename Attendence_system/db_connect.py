import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        host = "ballast.proxy.rlwy.net"
        user = "root"
        password = "IyzPANsHRQJWXmaWKHyHAZzlUnjAJEpl"
        database = "railway"
        port = 50532 

        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            port=port,
            auth_plugin='mysql_native_password'
        )
        
        if connection.is_connected():
            return connection

    except Error as e:
        print(f"Detailed Connection Error: {e}")
        return None
