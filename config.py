import os

# Telegram Bot Details
# Heroku ke "Config Vars" se value uthayega
API_ID = int(os.getenv("API_ID", "0")) 
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Admin & Logs
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

# Database
MONGO_URL = os.getenv("MONGO_URL", "")

# Father SMM API
SMM_API_URL = os.getenv("SMM_API_URL", "https://fathersmm.com/api/v2")
SMM_API_KEY = os.getenv("SMM_API_KEY", "")

# config.py mein ye line add kar de
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "gsk_TERI_KEY_YAHAN")
