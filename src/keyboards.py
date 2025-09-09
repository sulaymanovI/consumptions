from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from config import CATEGORIES

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить расход")],
            [KeyboardButton(text="📊 Мои расходы за неделю")],
            [KeyboardButton(text="📈 Общая статистика")],
            [KeyboardButton(text="📊 Экспорт в Excel")]
        ],
        resize_keyboard=True
    )

def get_categories_keyboard():
    buttons = []
    row = []
    for key, value in CATEGORIES.items():
        row.append(InlineKeyboardButton(text=value, callback_data=f"category_{key}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )