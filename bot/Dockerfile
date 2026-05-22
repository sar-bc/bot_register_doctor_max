# Используйте базовый образ Python
FROM python:3.10-slim

# Установите необходимые пакеты для локалей
RUN apt-get update && apt-get install -y locales && \
    echo "ru_RU.UTF-8 UTF-8" >> /etc/locale.gen && \
    locale-gen

# Установите локаль по умолчанию
ENV LANG=ru_RU.UTF-8
ENV LANGUAGE=ru_RU:ru
ENV LC_ALL=ru_RU.UTF-8

# Установите рабочую директорию
WORKDIR /bot

# Копируйте файл зависимостей
COPY requirements.txt .

# Установите зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируйте все файлы проекта
COPY . .

# Команда для запуска вашего приложения
CMD ["python", "main.py"]
