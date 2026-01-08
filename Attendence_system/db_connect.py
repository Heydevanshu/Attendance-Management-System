import os
import mysql.connector
from mysql.connector import Error

def get_connection():
    try:
        connection = mysql.connector.connect(
            host="ballast.proxy.rlwy.net",
            user="root",
            password="IyzPANsHRQJWXmaWKHyHAZzlUnjAJEpl",
            database="railway",
            port=50532,
            auth_plugin='mysql_native_password'
        )
        
        if connection.is_connected():
            print("Successfully connected to Railway DB!")
            return connection

    except Error as e:
        print(f"Detailed Connection Error: {e}")
        return None


