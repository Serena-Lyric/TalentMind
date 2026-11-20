CREATE TABLE IF NOT EXISTS job_definition (
    id INT PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL
);
INSERT INTO job_definition (id, job_name) VALUES (1, 'test-job');
