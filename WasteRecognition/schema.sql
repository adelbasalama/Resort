CREATE DATABASE IF NOT EXISTS waste_recognition
    CHARACTER SET utf8mb4;

USE waste_recognition;

CREATE TABLE IF NOT EXISTS recognition_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id VARCHAR(100) NOT NULL,
    submission_id VARCHAR(100) NOT NULL,
    model_id VARCHAR(100) NOT NULL,
    item_key VARCHAR(100) NOT NULL DEFAULT '',
    material VARCHAR(100) NOT NULL,
    confidence DOUBLE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'recognized',
    item_condition VARCHAR(20) NOT NULL DEFAULT 'unknown',
    special BOOLEAN NOT NULL DEFAULT FALSE,
    routing_code VARCHAR(20) NOT NULL DEFAULT 'REVIEW',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_attempt_id (attempt_id),
    CHECK (confidence BETWEEN 0 AND 1),
    CHECK (status IN ('recognized', 'uncertain', 'unsupported')),
    CHECK (item_condition IN ('clean', 'soiled', 'unknown')),
    CHECK (special IN (0, 1))
);
