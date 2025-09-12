-- Create the database
CREATE DATABASE witcher_rag CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Create a dedicated user (safer than root)
CREATE USER 'witcher'@'localhost' IDENTIFIED BY 'witcher_pw';

-- Grant privileges on this database to that user
GRANT ALL PRIVILEGES ON witcher_rag.* TO 'witcher'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;
