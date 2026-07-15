-- Создаем базу данных если не существует
CREATE DATABASE IF NOT EXISTS bot_doctor_max;
USE bot_doctor_max;

-- Создаем пользователя doctor с доступом с любого хоста
CREATE USER IF NOT EXISTS 'doctor'@'%' IDENTIFIED BY '159753';
GRANT ALL PRIVILEGES ON bot_doctor_max.* TO 'doctor'@'%';

-- Создаем root пользователя с доступом с любого хоста
CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY '159753';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;