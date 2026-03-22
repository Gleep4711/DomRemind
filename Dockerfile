FROM python:3.13-slim-bookworm

WORKDIR /code
COPY requirements.txt requirements.txt

COPY app app

COPY alembic alembic
COPY alembic.ini alembic.ini

COPY start.sh start.sh
RUN chmod +x start.sh

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

CMD ["./start.sh"]