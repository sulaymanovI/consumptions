from datetime import datetime
from database import db
from config import CATEGORIES, CHANNEL_ID
from aiogram import Bot

def format_amount(amount):
    """Форматирует сумму с пробелами для тысяч"""
    try:
        # Форматируем число с пробелами между тысячами
        return f"{amount:,.0f}".replace(",", " ").replace(".", " ")
    except (ValueError, TypeError):
        return str(amount)

async def send_weekly_report(bot: Bot):
    expenses = db.get_general_statistics()
    
    if not expenses:
        return
    
    report = "📈 Еженедельный отчет по расходам\n\n"
    
    # Группируем по пользователям
    users_data = {}
    for item in expenses:
        if item['first_name'] not in users_data:
            users_data[item['first_name']] = []
        users_data[item['first_name']].append(item)
    
    for user_name, user_expenses in users_data.items():
        total = sum(item['total_amount'] for item in user_expenses)
        report += f"👤 {user_name}:\n"
        
        for item in user_expenses:
            category_name = CATEGORIES.get(item['category'], item['category'])
            formatted_amount = format_amount(item['total_amount'])
            report += f"   {category_name}: {formatted_amount} сум ({item['expense_count']} покупок)\n"
        
        formatted_total = format_amount(total)
        report += f"   💵 Итого: {formatted_total} сум\n\n"
    
    # Отправляем в канал
    if CHANNEL_ID:
        await bot.send_message(CHANNEL_ID, report)