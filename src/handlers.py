from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
import asyncio
import os

from database import db
from keyboards import get_main_keyboard, get_categories_keyboard, get_cancel_keyboard
from config import CATEGORIES, ALLOWED_USERS, USER_NAMES
from models import Category
from utils import format_amount
from excel_utils import create_expenses_excel, cleanup_excel_file

router = Router()

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
        "• Смотреть статистику\n"
        "• Получать еженедельные отчеты\n"
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

@router.message(F.text == "📊 Мои расходы за неделю")
async def show_my_expenses(message: types.Message):
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    expenses = db.get_user_expenses_by_category(message.from_user.id)
    
    if not expenses:
        await message.answer("У вас нет расходов за эту неделю 📊")
        return
    
    total = sum(item['total_amount'] for item in expenses)
    response = "📊 Ваши расходы за неделю:\n\n"
    
    for item in expenses:
        category_name = CATEGORIES.get(item['category'], item['category'])
        formatted_amount = format_amount(item['total_amount'])
        response += f"{category_name}: {formatted_amount} сум ({item['expense_count']} раз)\n"
    
    formatted_total = format_amount(total)
    response += f"\n💵 Итого: {formatted_total} сум"
    await message.answer(response)

@router.message(F.text == "📈 Общая статистика")
async def show_general_statistics(message: types.Message):
    if not check_user_access(message.from_user.id):
        await send_access_denied(message)
        return
    
    expenses = db.get_general_statistics()
    
    if not expenses:
        await message.answer("Нет данных о расходах за эту неделю 📊")
        return
    
    # Группируем по пользователям
    users_data = {}
    for item in expenses:
        if item['first_name'] not in users_data:
            users_data[item['first_name']] = []
        users_data[item['first_name']].append(item)
    
    response = "📈 Общая статистика расходов за неделю:\n\n"
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

class ExpenseStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_description = State()
    waiting_for_category = State()
    waiting_for_comment = State()

# Обработчики состояний тоже нужно защитить
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