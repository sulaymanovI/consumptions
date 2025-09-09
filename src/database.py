import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG
from models import Category

class Database:
    def __init__(self):
        self.connection = None
        self.connect()
        self.init_db()

    def connect(self):
        try:
            # Добавляем SSL параметры если они есть в конфиге
            connection_params = DB_CONFIG.copy()
            if 'sslmode' in connection_params:
                # Для Aiven обычно требуется SSL
                connection_params['sslmode'] = 'require'
                connection_params['sslrootcert'] = 'path/to/ca.crt'  # если нужно
            
            self.connection = psycopg2.connect(**connection_params)
            print("Connected to PostgreSQL database successfully!")
            print(f"Database: {DB_CONFIG.get('dbname')}")
            print(f"Host: {DB_CONFIG.get('host')}")
        except Exception as e:
            print(f"Error connecting to database: {e}")
            print("Connection parameters:", {k: v for k, v in DB_CONFIG.items() if k != 'password'})

    def init_db(self):
        try:
            with self.connection.cursor() as cursor:
                # Таблица пользователей
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        telegram_id BIGINT UNIQUE NOT NULL,
                        username VARCHAR(100),
                        first_name VARCHAR(100),
                        last_name VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Таблица расходов
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS expenses (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER REFERENCES users(id),
                        amount DECIMAL(10, 2) NOT NULL,
                        category VARCHAR(20) NOT NULL,
                        description TEXT NOT NULL,
                        comment TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                self.connection.commit()
                print("Database initialized successfully")
        except Exception as e:
            print(f"Error initializing database: {e}")

    # Остальные методы остаются без изменений...
    def add_user(self, telegram_id: int, username: str, first_name: str, last_name: str = None):
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO users (telegram_id, username, first_name, last_name)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (telegram_id) DO NOTHING
                    RETURNING id
                """, (telegram_id, username, first_name, last_name))
                self.connection.commit()
        except Exception as e:
            print(f"Error adding user: {e}")

    def add_expense(self, telegram_id: int, amount: float, category: Category, description: str, comment: str = None):
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                user = cursor.fetchone()
                
                if user:
                    cursor.execute("""
                        INSERT INTO expenses (user_id, amount, category, description, comment)
                        VALUES (%s, %s, %s, %s, %s)
                        RETURNING id
                    """, (user[0], amount, category.value, description, comment))
                    self.connection.commit()
                    return True
            return False
        except Exception as e:
            print(f"Error adding expense: {e}")
            return False

    def get_weekly_expenses(self):
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        u.first_name,
                        e.category,
                        SUM(e.amount) as total_amount,
                        COUNT(e.id) as expense_count
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    WHERE e.created_at >= DATE_TRUNC('week', CURRENT_DATE)
                    GROUP BY u.first_name, e.category
                    ORDER BY u.first_name, total_amount DESC
                """)
                return cursor.fetchall()
        except Exception as e:
            print(f"Error getting weekly expenses: {e}")
            return []

    def get_user_expenses_by_category(self, telegram_id: int):
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        e.category,
                        SUM(e.amount) as total_amount,
                        COUNT(e.id) as expense_count
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    WHERE u.telegram_id = %s 
                    AND e.created_at >= DATE_TRUNC('week', CURRENT_DATE)
                    GROUP BY e.category
                    ORDER BY total_amount DESC
                """, (telegram_id,))
                return cursor.fetchall()
        except Exception as e:
            print(f"Error getting user expenses: {e}")
            return []
    def get_general_statistics(self):
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        u.first_name,
                        e.category,
                        SUM(e.amount) as total_amount,
                        COUNT(e.id) as expense_count
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    WHERE e.created_at >= DATE_TRUNC('week', CURRENT_DATE)
                    GROUP BY u.first_name, e.category
                    ORDER BY u.first_name, total_amount DESC
                """)
                return cursor.fetchall()
        except Exception as e:
            print(f"Error getting general statistics: {e}")
            return []  
          
    def get_all_expenses(self):
        """Получает все расходы (только основные поля для оптимизации)"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        u.first_name,
                        e.amount,
                        e.category,
                        e.description,
                        e.comment,
                        e.created_at
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    ORDER BY e.created_at DESC
                """)
                return cursor.fetchall()
        except Exception as e:
            print(f"Error getting all expenses: {e}")
            return []

db = Database()