import telebot
import requests
from bs4 import BeautifulSoup
import sqlite3
import re
import os

token = os.getenv('BOT_TOKEN', 'Your token')
bot = telebot.TeleBot(token)

url = 'https://auto.ria.com/uk/'
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_car(query_brand=None, max_price=None):
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, 'lxml')

    cars = soup.find_all('div', class_='text-template-builder')
    car_list = []

    processed_links = set()

    for car in cars:
        try:
            parent_link = car.find_parent('a', class_='action-wrapper-link')
            if not parent_link:
                continue

            href = parent_link.get('href')
            if href and not href.startswith('http'):
                link = f'https://auto.ria.com{href}'
            else:
                link = href

            if link in processed_links:
                continue

            name_tag = car.find('span', class_='common-text')
            if name_tag:
                name = name_tag.text.strip()
                if '•' in name or 'грн' in name:
                    continue
            else:
                continue

            if query_brand and query_brand.lower() not in name.lower():
                continue

            price_tag = parent_link.find('span', class_='body')
            price_tag_d = parent_link.find('strong', class_='titleM')
            
            if not price_tag:
                price_tag = parent_link.find('div', class_='price-ticket')
                
            if price_tag and price_tag_d:
                price = price_tag.text.strip().replace('•', '').strip()
                price_d = price_tag_d.text.strip().replace('•', '').strip()
                if max_price and price_d:
                    numeric_price = int(re.sub(r'\D', '', price_d))
                    if numeric_price > max_price:
                        continue
            else:
                price = "Цена в описании"
                price_d = ''

            full_info = f"🚗 {name}\n💰 Цена: {price} / {price_d}\n🔗 Ссылка: {link}"
            
            processed_links.add(link)
            car_list.append(full_info)

        except Exception as e:
            continue

    return car_list


def init_db():
    conn = sqlite3.connect('cars.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cars (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_price TEXT UNIQUE
        )
    ''')
    conn.commit()
    conn.close()

def is_new_car(car_text):
    conn = sqlite3.connect('cars.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM cars WHERE name_price = ?', (car_text,))
    car_info = cursor.fetchone()
    if not car_info:
        cursor.execute('INSERT INTO cars (name_price) VALUES (?)', (car_text,))
        conn.commit()
        conn.close()
        return True
    else:
        conn.close()
        return False

@bot.message_handler(commands=['start'])
def start(message):
    text = (
        'Привет, бро! Я ищу тачки.\n\n'
        '👉 Нажми /get, чтобы проверить ВСЕ новые тачки.\n'
        '👉 Напиши `/find [марка] [цена]`, чтобы найти конкретную тачку.\n'
        'Пример: `/find Lexus 50000`'
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['get'])
def get(message):
    bot.reply_to(message, 'Запускаю сканирование...')
    found_car = get_car()
    new_cars_count = 0

    for car in found_car:
        if is_new_car(car):
            bot.send_message(message.chat.id, f'Новая тачка: {car}')
            new_cars_count += 1

    if new_cars_count == 0:
        bot.send_message(message.chat.id, '✅ Новых тачек на рынке пока нет')

@bot.message_handler(commands=['find'])
def find(message):
    argyments = message.text.split()

    if len(argyments) < 3:
        bot.reply_to(message, 'Бро, пиши команду правильно!\nПример: `/find BMW 15000`', parse_mode='Markdown')
        return
    
    brand = argyments[1]
    try:
        max_price = int(argyments[2])
    except ValueError:
        bot.reply_to(message, 'Бюджет должен быть числом! Пример: `15000`', parse_mode='Markdown')
        return
    
    bot.reply_to(message, f'🔍 Ищу тачки марки *{brand}* до *${max_price}*...', parse_mode='Markdown')

    found_car = get_car(query_brand=brand, max_price=max_price)
    new_cars_count = 0

    for car in found_car:
        if is_new_car(car):
            bot.send_message(message.chat.id, f'Новая тачка по вашему фильтру:\n{car}')
            new_cars_count += 1

    if new_cars_count == 0:
        bot.send_message(message.chat.id, f'❌ Ничего нового по запросу {brand} до ${max_price} не найдено.')
    
print('Бот запущен')
init_db()
bot.infinity_polling()
