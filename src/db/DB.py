import mysql.connector

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Y1234567',
    'database': 'bike_routes'
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                name VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS routes (
                route_id INT AUTO_INCREMENT PRIMARY KEY,
                start_lat DOUBLE NOT NULL,
                start_lon DOUBLE NOT NULL,
                end_lat DOUBLE NOT NULL,
                end_lon DOUBLE NOT NULL,
                user_id INT NOT NULL,
                max_slope DOUBLE DEFAULT NULL,
                total_slope DOUBLE DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS route_paths (
                path_id INT AUTO_INCREMENT PRIMARY KEY,
                route_id INT NOT NULL,
                path_json JSON NOT NULL,
                FOREIGN KEY (route_id) REFERENCES routes(route_id)
            )
        ''')

        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Database initialized")
    except mysql.connector.Error as err:
        print(f"❌ Database error: {err}")

if __name__ == '__main__':
    init_db()