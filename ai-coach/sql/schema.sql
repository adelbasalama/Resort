CREATE DATABASE IF NOT EXISTS waste_assistant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE waste_assistant;
CREATE TABLE IF NOT EXISTS regions (
  id VARCHAR(64) PRIMARY KEY, name VARCHAR(160) NOT NULL,
  source_url VARCHAR(500) NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS recycling_rules (
  id BIGINT AUTO_INCREMENT PRIMARY KEY, region_id VARCHAR(64) NOT NULL,
  item_key VARCHAR(100) NOT NULL, category ENUM('recyclable','compostable','landfill','special') NOT NULL,
  bin_label VARCHAR(160) NOT NULL, preparation TEXT NOT NULL, source_url VARCHAR(500) NOT NULL,
  reviewed_on DATE NOT NULL, version INT NOT NULL DEFAULT 1,
  condition_label ENUM('any','clean','soiled','unknown') NOT NULL DEFAULT 'any',
  active BOOLEAN NOT NULL DEFAULT TRUE,
  active_rule_key VARCHAR(300) GENERATED ALWAYS AS
    (IF(active, CONCAT(region_id, ':', item_key, ':', condition_label), NULL)) STORED,
  CONSTRAINT fk_rule_region FOREIGN KEY (region_id) REFERENCES regions(id),
  UNIQUE KEY one_rule_version (region_id,item_key,condition_label,version),
  UNIQUE KEY one_active_rule (active_rule_key)
);
INSERT IGNORE INTO regions(id,name,source_url) VALUES
 ('demo-dortmund','Dortmund (demo rules)','https://www.dortmund.de/');
INSERT IGNORE INTO recycling_rules(region_id,item_key,category,bin_label,preparation,source_url,reviewed_on,version,condition_label) VALUES
 ('demo-dortmund','beverage_can','recyclable','Yellow recycling bin','Empty the can. Do not crush it.','https://www.dortmund.de/',CURRENT_DATE,1,'any'),
 ('demo-dortmund','banana_peel','compostable','Organic waste bin','Remove stickers and place the peel with organic waste.','https://www.dortmund.de/',CURRENT_DATE,1,'any'),
 ('demo-dortmund','battery','special','Battery collection point','Never place batteries in household bins. Use an authorized collection point.','https://www.dortmund.de/',CURRENT_DATE,1,'any'),
 ('demo-dortmund','plastic_bottle','recyclable','Packaging collection','Check deposit return and local accepted plastics.','https://www.dortmund.de/',CURRENT_DATE,1,'any'),
 ('demo-dortmund','plastic_container','recyclable','Packaging collection','Empty the container. Check local accepted plastics.','https://www.dortmund.de/',CURRENT_DATE,1,'any'),
 ('demo-dortmund','paper_bag','recyclable','Paper collection','Keep paper clean and dry. Remove non-paper lining.','https://www.dortmund.de/',CURRENT_DATE,1,'any'),
 ('demo-dortmund','glass_bottle','recyclable','Glass collection point','Check deposit return first. Check local colour separation.','https://www.dortmund.de/',CURRENT_DATE,1,'any');
