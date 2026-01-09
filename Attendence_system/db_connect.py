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
        return connection
    except Exception as e:
        print(f"Error: {e}")
        return None
