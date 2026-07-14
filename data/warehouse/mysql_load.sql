-- Put this project directory on the MySQL client machine before running.
-- MySQL may require: SET GLOBAL local_infile = 1;

USE job_kg;

LOAD DATA LOCAL INFILE 'data/etl/unified_jobs.csv'
INTO TABLE job_postings
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/etl/unified_job_skills.csv'
INTO TABLE job_skill_evidence
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/kg/nodes.csv'
INTO TABLE kg_nodes
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/kg/edges.csv'
INTO TABLE kg_edges
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES
(id, from_id, to_id, type, weight, confidence, first_seen, last_seen, evidence);

LOAD DATA LOCAL INFILE 'data/kg/skill_trends.csv'
INTO TABLE skill_trends
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;

LOAD DATA LOCAL INFILE 'data/etl/data_quality_report.csv'
INTO TABLE data_quality_report
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;
