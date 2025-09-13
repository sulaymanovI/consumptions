import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG
from models import Category
import time
import logging

class Database:
    def __init__(self):
        self.connection = None
        self.max_retries = 3
        self.retry_delay = 2
        self.connect()
        self.init_db()

    def connect(self):
        for attempt in range(self.max_retries):
            try:
                self.connection = psycopg2.connect(**DB_CONFIG)
                logging.info("Connected to PostgreSQL database successfully!")
                logging.info(f"Database: {DB_CONFIG.get('dbname')}")
                logging.info(f"Host: {DB_CONFIG.get('host')}")
                return
            except Exception as e:
                logging.info(f"Error connecting to database (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logging.info("Failed to connect to PostgreSQL after multiple attempts")
                    raise e

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
                logging.info("Database initialized successfully")
        except Exception as e:
            logging.info(f"Error initializing database: {e}")

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
            logging.info(f"Error adding user: {e}")

    def add_expense(self, telegram_id: int, amount: float, category: Category, description: str, comment: str = None):
        try:
            with self.connection.cursor() as cursor:
                # Получаем user_id
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
            logging.info(f"Error adding expense: {e}")
            return False

    def get_user_expenses_by_category_weekly(self, telegram_id: int):
        """Получает расходы пользователя по категориям за текущую неделю (PostgreSQL)"""
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
            logging.info(f"Error getting user weekly expenses: {e}")
            return []

    def get_user_expenses_by_category_all_time(self, telegram_id: int):
        """Получает расходы пользователя по категориям за всё время"""
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
                    GROUP BY e.category
                    ORDER BY total_amount DESC
                """, (telegram_id,))
                return cursor.fetchall()
        except Exception as e:
            logging.info(f"Error getting user all-time expenses: {e}")
            return []

    def get_general_statistics_weekly(self):
        """Получает общую статистику расходов за текущую неделю (PostgreSQL)"""
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
            logging.info(f"Error getting general weekly statistics: {e}")
            return []

    def get_general_statistics_all_time(self):
        """Получает общую статистику расходов за всё время"""
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
                    GROUP BY u.first_name, e.category
                    ORDER BY u.first_name, total_amount DESC
                """)
                return cursor.fetchall()
        except Exception as e:
            logging.info(f"Error getting general all-time statistics: {e}")
            return []

    def get_all_expenses(self):
        """Получает все расходы со всей информацией"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        u.first_name,
                        u.username,
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
            logging.info(f"Error getting all expenses: {e}")
            return []
    def get_expenses_by_date(self, telegram_id: int, target_date: str):
        """Получает расходы пользователя за конкретную дату"""
        try:
            with self.connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT 
                        e.category,
                        e.amount,
                        e.description,
                        e.comment,
                        e.created_at
                    FROM expenses e
                    JOIN users u ON e.user_id = u.id
                    WHERE u.telegram_id = %s 
                    AND DATE(e.created_at) = %s
                    ORDER BY e.created_at DESC
                """, (telegram_id, target_date))
                return cursor.fetchall()
        except Exception as e:
            logging.info(f"Error getting expenses by date: {e}")
            return []

# Глобальный экземпляр базы данных
db = Database()