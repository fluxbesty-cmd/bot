# Конфигурация бота
import os
from dotenv import load_dotenv

load_dotenv()

# Токен сообщества VK (получить здесь: https://vk.com/editapp?act=tokens)
VK_TOKEN = os.getenv("VK_TOKEN", "YOUR_VK_TOKEN")

# Настройки Bitrix24
BITRIX_WEBHOOK = os.getenv("BITRIX_WEBHOOK", "https://your-bitrix24.bitrix24.ru/rest/1/YOUR_WEBHOOK_CODE/")
BITRIX_API_KEY = os.getenv("BITRIX_API_KEY", "YOUR_BITRIX_API_KEY")

# Ссылка на Calendly
CALENDLY_LINK = os.getenv("CALENDLY_LINK", "https://calendly.com/your-link")

# ID группы VK (числовой, без "club")
VK_GROUP_ID = os.getenv("VK_GROUP_ID", "123456789")

# Путь к файлу логов
LOG_FILE = "logs/bot.log"   