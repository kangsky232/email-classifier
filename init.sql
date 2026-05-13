CREATE DATABASE IF NOT EXISTS mail_system DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE mail_system;

CREATE TABLE IF NOT EXISTS emails (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sender VARCHAR(255) NOT NULL,
    subject VARCHAR(500),
    content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS classifications (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email_id INT NOT NULL,
    agent_name VARCHAR(50),
    method VARCHAR(50),
    category VARCHAR(50),
    confidence FLOAT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS paxos_logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email_id INT NOT NULL,
    proposal_id INT,
    phase VARCHAR(20),
    proposer VARCHAR(50),
    value VARCHAR(100),
    result VARCHAR(20),
    acceptor_votes JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS final_results (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email_id INT NOT NULL UNIQUE,
    category VARCHAR(50),
    method VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (email_id) REFERENCES emails(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) NOT NULL UNIQUE,
    config_value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO system_config (config_key, config_value) VALUES
('categories', '["会议通知", "垃圾邮件", "工作汇报", "可疑邮件"]'),
('paxos_acceptor_count', '3'),
('paxos_timeout_ms', '5000'),
('paxos_retry_count', '3'),
('agent_min_count', '2')
ON DUPLICATE KEY UPDATE config_value = VALUES(config_value);
