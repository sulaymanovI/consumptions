from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, ReplyKeyboardMarkup, KeyboardButton
import asyncio
import os
from datetime import datetime, timedelta

from database import db
from keyboards import get_categories_keyboard, get_cancel_keyboard
from config import CATEGORIES, ALLOWED_USERS, USER_NAMES
from models import Category
from utils import format_amount
from excel_utils import create_expenses_excel, cleanup_excel_file

router = Router()

# Класс состояний должен быть объявлен в начале
class ExpenseStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_description = State()
    waiting_for_category = State()
    waiting_for_comment = State()
    waiting_for_date = State()  # Новое состояние для ввода даты

def get_main_keyboard():
    """Главная клавиатура с новыми кнопками"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Добавить расход")],
            [KeyboardButton(text="📊 Мои расходы за неделю")],
            [KeyboardButton(text="📈 Общая статистика за неделю")],
            [KeyboardButton(text="💾 Все мои расходы")],
            [KeyboardButton(text="🏆 Общая статистика за всё время")],
            [KeyboardButton(text="📅 Расходы по дате")],
            [KeyboardButton(text="📊 Экспорт в Excel")]
        ],
        resize_keyboard=True
    )

def check_user_access(user_id: int) -> bool:
    """Проверяет доступ пользователя"""
    return user_id in ALLOWED_USERS

async def send_access_denied(message: types.Message):
    """Отправляет сообщение о запрете доступа"""
    await message.answer(
        "⛔ Доступ запрещен!\n\n"
        "Этот бот предназначен только для личного использования. "
        "Если вы считаете, что получили это сообщение по ошибке, "
        "свяжитесь с администратором."
    )

# Добавим команду для получения ID
@router.message(Command("myid"))
async def get_my_id(message: types.Message):
    await message.answer(f"Ваш ID: {message.from_user.id}")

@router.message(Command("start", "help"))
async def start_command(message: types.Message):
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    db.add_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name
    )
    
    user_name = USER_NAMES.get(message.from_user.id, message.from_user.first_name)
    await message.answer(
        f"💰 Добро пожаловать, {user_name}!\n\n"
        "Вы можете:\n"
        "• Добавлять расходы\n"
        "• Смотреть статистику за неделю\n"
        "• Смотреть общую статистику\n"
        "• Посмотреть расходы по конкретной дате\n"
        "• Экспортировать данные в Excel",
        reply_markup=get_main_keyboard()
    )

@router.message(F.text == "➕ Добавить расход")
async def add_expense_command(message: types.Message, state: FSMContext):
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    await state.set_state(ExpenseStates.waiting_for_amount)
    await message.answer(
        "Введите сумму расхода:",
        reply_markup=get_cancel_keyboard()
    )

@router.message(F.text == "📅 Расходы по дате")
async def ask_for_date(message: types.Message, state: FSMContext):
    """Запрашивает дату для просмотра расходов"""
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    await state.set_state(ExpenseStates.waiting_for_date)
    await message.answer(
        "📅 Введите дату в формате ГГГГ-ММ-ДД\n\n"
        "Например: 2024-01-15\n"
        "Или введите 'сегодня' для сегодняшней даты",
        reply_markup=get_cancel_keyboard()
    )

@router.message(ExpenseStates.waiting_for_date)
async def show_expenses_by_date(message: types.Message, state: FSMContext):
    """Показывает расходы за указанную дату"""
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    date_input = message.text.strip().lower()
    
    # Обработка специальных команд
    if date_input == 'сегодня':
        target_date = datetime.now().strftime("%Y-%m-%d")
    elif date_input == 'вчера':
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        # Проверяем корректность формата даты
        try:
            datetime.strptime(date_input, "%Y-%m-%d")
            target_date = date_input
        except ValueError:
            await message.answer(
                "❌ Неверный формат даты!\n\n"
                "Пожалуйста, введите дату в формате ГГГГ-ММ-ДД\n"
                "Например: 2024-01-15\n"
                "Или введите 'сегодня'"
            )
            return
    
    # Получаем расходы за указанную дату
    expenses = db.get_expenses_by_date(message.from_user.id, target_date)
    
    if not expenses:
        await message.answer(
            f"📊 Нет расходов за {target_date}",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        return
    
    total = sum(float(item['amount']) for item in expenses)
    response = f"📅 Ваши расходы за {target_date}:\n\n"
    
    for i, item in enumerate(expenses, 1):
        category_name = CATEGORIES.get(item['category'], item['category'])
        formatted_amount = format_amount(item['amount'])
        time_str = item['created_at'].strftime("%H:%M") if isinstance(item['created_at'], datetime) else ""
        
        response += f"{i}. {category_name}: {formatted_amount} сум\n"
        response += f"   Описание: {item['description']}\n"
        if item['comment']:
            response += f"   Комментарий: {item['comment']}\n"
        if time_str:
            response += f"   Время: {time_str}\n"
        response += "\n"
    
    formatted_total = format_amount(total)
    response += f"💵 Итого за день: {formatted_total} сум"
    
    await message.answer(response, reply_markup=get_main_keyboard())
    await state.clear()

@router.message(F.text == "📊 Мои расходы за неделю")
async def show_my_expenses_weekly(message: types.Message):
    """Мои расходы за текущую неделю"""
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    expenses = db.get_user_expenses_by_category_weekly(message.from_user.id)
    
    if not expenses:
        await message.answer("У вас нет расходов за эту неделю 📊")
        return
    
    total = sum(item['total_amount'] for item in expenses)
    response = "📊 Ваши расходы за текущую неделю:\n\n"
    
    for item in expenses:
        category_name = CATEGORIES.get(item['category'], item['category'])
        formatted_amount = format_amount(item['total_amount'])
        response += f"{category_name}: {formatted_amount} сум ({item['expense_count']} раз)\n"
    
    formatted_total = format_amount(total)
    response += f"\n💵 Итого за неделю: {formatted_total} сум"
    await message.answer(response)

@router.message(F.text == "💾 Все мои расходы")
async def show_my_expenses_all_time(message: types.Message):
    """Все мои расходы за всё время"""
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    expenses = db.get_user_expenses_by_category_all_time(message.from_user.id)
    
    if not expenses:
        await message.answer("У вас нет расходов 📊")
        return
    
    total = sum(item['total_amount'] for item in expenses)
    response = "💾 Все ваши расходы:\n\n"
    
    for item in expenses:
        category_name = CATEGORIES.get(item['category'], item['category'])
        formatted_amount = format_amount(item['total_amount'])
        response += f"{category_name}: {formatted_amount} сум ({item['expense_count']} раз)\n"
    
    formatted_total = format_amount(total)
    response += f"\n💵 Общий итог: {formatted_total} сум"
    await message.answer(response)

@router.message(F.text == "📈 Общая статистика за неделю")
async def show_general_statistics_weekly(message: types.Message):
    """Общая статистика расходов за текущую неделю"""
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    expenses = db.get_general_statistics_weekly()
    
    if not expenses:
        await message.answer("Нет данных о расходах за эту неделю 📊")
        return
    
    # Группируем по пользователям
    users_data = {}
    for item in expenses:
        if item['first_name'] not in users_data:
            users_data[item['first_name']] = []
        users_data[item['first_name']].append(item)
    
    response = "📈 Общая статистика расходов за текущую неделю:\n\n"
    grand_total = 0
    
    for user_name, user_expenses in users_data.items():
        user_total = sum(item['total_amount'] for item in user_expenses)
        grand_total += user_total
        
        response += f"👤 {user_name}:\n"
        
        for item in user_expenses:
            category_name = CATEGORIES.get(item['category'], item['category'])
            formatted_amount = format_amount(item['total_amount'])
            response += f"   {category_name}: {formatted_amount} сум ({item['expense_count']} покупок)\n"
        
        formatted_user_total = format_amount(user_total)
        response += f"   💵 Итого: {formatted_user_total} сум\n\n"
    
    formatted_grand_total = format_amount(grand_total)
    response += f"🏆 Общая сумма за неделю: {formatted_grand_total} сум"
    await message.answer(response)

@router.message(F.text == "🏆 Общая статистика за всё время")
async def show_general_statistics_all_time(message: types.Message):
    """Общая статистика расходов за всё время"""
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    expenses = db.get_general_statistics_all_time()
    
    if not expenses:
        await message.answer("Нет данных о расходах 📊")
        return
    
    # Группируем по пользователям
    users_data = {}
    for item in expenses:
        if item['first_name'] not in users_data:
            users_data[item['first_name']] = []
        users_data[item['first_name']].append(item)
    
    response = "🏆 Общая статистика расходов за всё время:\n\n"
    grand_total = 0
    
    for user_name, user_expenses in users_data.items():
        user_total = sum(item['total_amount'] for item in user_expenses)
        grand_total += user_total
        
        response += f"👤 {user_name}:\n"
        
        for item in user_expenses:
            category_name = CATEGORIES.get(item['category'], item['category'])
            formatted_amount = format_amount(item['total_amount'])
            response += f"   {category_name}: {formatted_amount} сум ({item['expense_count']} покупок)\n"
        
        formatted_user_total = format_amount(user_total)
        response += f"   💵 Итого: {formatted_user_total} сум\n\n"
    
    formatted_grand_total = format_amount(grand_total)
    response += f"🏆 Общая сумма всех расходов: {formatted_grand_total} сум"
    await message.answer(response)

@router.message(F.text == "📊 Экспорт в Excel")
async def export_to_excel(message: types.Message):
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    excel_file_path = None
    
    try:
        await message.answer("🔄 Создаем отчет...")
        expenses = db.get_all_expenses()
        
        if not expenses:
            await message.answer("Нет данных о расходах для экспорта 📊")
            return
        
        # Создаем Excel файл
        excel_file_path = create_expenses_excel(expenses)
        
        # Читаем файл и создаем BufferedInputFile
        with open(excel_file_path, 'rb') as file:
            file_data = file.read()
        
        # Создаем документ для отправки
        document = BufferedInputFile(
            file=file_data,
            filename="expenses_report.xlsx"
        )
        
        # Отправляем файл
        await message.answer_document(
            document=document,
            caption=f"📊 Отчет по расходам\n\n"
                   f"Всего записей: {len(expenses)}\n"
                   f"Общая сумма: {format_amount(sum(float(expense['amount']) for expense in expenses))} сум"
        )
        
    except Exception as e:
        await message.answer("❌ Произошла ошибка при создании отчета")
        print(f"Error creating Excel report: {e}")
        
    finally:
        # Очищаем временный файл
        if excel_file_path:
            cleanup_excel_file(excel_file_path)

@router.message(F.text == "❌ Отмена")
async def cancel_handler(message: types.Message, state: FSMContext):
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    await state.clear()
    await message.answer("Действие отменено", reply_markup=get_main_keyboard())

# Обработчики состояний
@router.message(ExpenseStates.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    try:
        amount = float(message.text.replace(',', '.').replace(' ', ''))
        if amount <= 0:
            raise ValueError
        
        await state.update_data(amount=amount)
        await state.set_state(ExpenseStates.waiting_for_description)
        await message.answer("Опишите расход (например: 'Обед в кафе'):")
    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму:")

@router.message(ExpenseStates.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    await state.update_data(description=message.text)
    await state.set_state(ExpenseStates.waiting_for_category)
    await message.answer("Выберите категорию:", reply_markup=get_categories_keyboard())

@router.callback_query(ExpenseStates.waiting_for_category, F.data.startswith("category_"))
async def process_category(callback: types.CallbackQuery, state: FSMContext):
    if not check_user_access(callback.from_user.id):
        await callback.message.answer("⛔ Доступ запрещен!")
        return
    
    category = callback.data.split('_')[1]
    await state.update_data(category=category)
    await state.set_state(ExpenseStates.waiting_for_comment)
    await callback.message.answer(
        "Хотите добавить комментарий? (Если нет, отправьте 'нет')",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.message(ExpenseStates.waiting_for_comment)
async def process_comment(message: types.Message, state: FSMContext):
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    data = await state.get_data()
    comment = message.text if message.text.lower() != 'нет' else None
    
    success = db.add_expense(
        message.from_user.id,
        data['amount'],
        Category(data['category']),
        data['description'],
        comment
    )
    
    if success:
        category_name = CATEGORIES[data['category']]
        formatted_amount = format_amount(data['amount'])
        await message.answer(
            f"✅ Расход добавлен!\n"
            f"Сумма: {formatted_amount} сум\n"
            f"Категория: {category_name}\n"
            f"Описание: {data['description']}\n"
            f"Комментарий: {comment if comment else 'нет'}",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer(
            "❌ Ошибка при добавлении расхода",
            reply_markup=get_main_keyboard()
        )
    
    await state.clear()