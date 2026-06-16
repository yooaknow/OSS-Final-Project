CREATE DATABASE IF NOT EXISTS travel_rec;
USE travel_rec;

CREATE USER IF NOT EXISTS 'recuser'@'%' IDENTIFIED BY 'recpass';
GRANT ALL PRIVILEGES ON travel_rec.* TO 'recuser'@'%';
FLUSH PRIVILEGES;

CREATE TABLE IF NOT EXISTS cafe_recommendation_history (
    id                     INT AUTO_INCREMENT PRIMARY KEY,
    weather                VARCHAR(20) NOT NULL,
    mood                   VARCHAR(20) NOT NULL,
    sweetness              INT NOT NULL,
    caffeine_sensitivity   INT NOT NULL,
    time_of_day            VARCHAR(20) NOT NULL,
    results_json           JSON,
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
