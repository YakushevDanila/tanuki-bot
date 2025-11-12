import os

# Часовой пояс (Москва)
TIMEZONE = os.getenv('TIMEZONE', 'Europe/Moscow')

# ID пользователя для уведомлений (можно получить через /myid)
USER_ID = int(os.getenv('USER_ID', '0'))

# Проверяем обязательные переменные для уведомлений
if not USER_ID:
    print("⚠️  USER_ID not set - notifications will be disabled")

