# DomRemind

DomRemind is a Telegram bot for tracking domain expiration dates, sending reminders, and managing domains in one place.

For domain checks, the project uses `whodap` for RDAP zones and `whois21` for custom WHOIS parsing.

## Features

- Add and manage domains directly from Telegram
- Check expiration dates via WHOIS / RDAP sources
- Receive expiration reminders in Telegram
- Connect Cloudflare and import domains automatically
- Support multiple users and role-based access
- Basic admin statistics and user management

## Roles

- `guest`: access to domain management, with a limit of 10 domains
- `user`: access to domains and Cloudflare features
- `admin`: access to user management and general statistics

## Requirements

- Python 3.13+
- PostgreSQL
- Telegram bot token

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Gleep4711/DomRemind.git
cd DomRemind
```

or

```bash
git clone git@github.com:Gleep4711/DomRemind.git
cd DomRemind
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file with the required values:

```env
BOT_TOKEN=your_telegram_bot_token
DB_URL=postgresql+psycopg://user:password@host:5432/dbname
ADMIN=your_telegram_user_id
LOGGING=INFO
```

### 4. Apply database migrations

```bash
alembic upgrade head
```

### 5. Run the bot

```bash
python -m app
```

## Docker

You can run the project with Docker Compose:

```bash
docker compose up --build
```

## Usage

### Main commands

- `/start` show available commands for your role
- `/add_domain` add one or more domains
- `/get_domains` show tracked domains
- `/remove_domains` remove a domain
- `/add_cloud_token` add a Cloudflare token
- `/get_cloud_tokens` show saved Cloudflare tokens
- `/help_create_new_token` show Cloudflare token setup instructions

### Admin commands

- `/get_users` show all users with their roles and domain counts
- `/get_stats` show general bot statistics

## Notes

- Guests can manage domains, but are limited to 10 domains
- Users and admins are not limited by domain count
- Cloudflare features are available only for `user` and `admin`
- Domain checks depend on external services and may occasionally be incomplete or outdated

## License

This repository includes the [LICENSE](/home/gleep/work/DomRemind/LICENSE) file and is distributed under the Unlicense.

In practical terms:

- the project is released into the public domain where possible
- the software is provided `AS IS`
- there is no warranty of any kind
- the author is not liable for damages, losses, missed renewals, incorrect notifications, or any consequences of using this software

If you need different licensing terms, you should replace the current license with one that matches your intended distribution model.
