# DomRemind 🏷️

Telegram-bot for reminding the imminent end of domains.

## 📌 Possibilities

- Checks the validity of domains through Whois API.
- Send notifications to Telegram to the day before the expiration.
- Support for several domains.

## 🚀 Installation
### 1. Cloning the repository:

```bash
git clone https://github.com/yourusername/DomRemind.git
cd DomRemind
```

### 2. Installation of addictions:

```bash
pip install -r requirements.txt
```

### 3. Setting up the environment variables:

Create `.env` file and indicate:

```env
BOT_TOKEN=your_telegram_bot_token
```

### 4. Launch of the bot:

```bash
python bot.py
```

## ⚙️ Usage
1. Add the bot to Telegram.
2. Send the `/add example.com team to track the domain.
3. The bot will notify you of n days before the expiration.
