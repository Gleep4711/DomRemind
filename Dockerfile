FROM python:3.13-slim-bookworm

WORKDIR /code
COPY requirements.txt /code/requirements.txt
COPY app /code/app
COPY alembic /code/alembic
COPY alembic.ini /code/alembic.ini
COPY .env /code/.env

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

CMD alembic upgrade heads && python -m bot