CREATE DATABASE IF NOT EXISTS badminton_db
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE badminton_db;

CREATE TABLE location (
  location_id INT AUTO_INCREMENT PRIMARY KEY,
  name        VARCHAR(100) NOT NULL,
  address     VARCHAR(255),
  city        VARCHAR(100) NOT NULL,
  state       VARCHAR(100),
  country     VARCHAR(100) NOT NULL DEFAULT 'USA',
  postal_code VARCHAR(20),
  UNIQUE KEY uq_location (name, city)
);

CREATE TABLE ground (
  ground_id   INT AUTO_INCREMENT PRIMARY KEY,
  location_id INT NOT NULL,
  name        VARCHAR(100) NOT NULL,
  surface     ENUM('wooden','synthetic','cement','other') NOT NULL DEFAULT 'wooden',
  is_indoor   BOOLEAN NOT NULL DEFAULT TRUE,
  total_courts INT NOT NULL CHECK (total_courts > 0),
  hourly_rate DECIMAL(8,2) NOT NULL DEFAULT 0,
  FOREIGN KEY (location_id) REFERENCES location(location_id)
);

CREATE TABLE court (
  court_id   INT AUTO_INCREMENT PRIMARY KEY,
  ground_id  INT NOT NULL,
  court_no   INT NOT NULL,
  status     ENUM('active','maintenance','closed') NOT NULL DEFAULT 'active',
  UNIQUE KEY uq_court (ground_id, court_no),
  FOREIGN KEY (ground_id) REFERENCES ground(ground_id)
);

CREATE TABLE group_type (
  group_type_id INT AUTO_INCREMENT PRIMARY KEY,
  name          VARCHAR(50) NOT NULL UNIQUE,
  description   VARCHAR(255),
  min_age       INT,
  max_age       INT
);

CREATE TABLE trainer (
  trainer_id  INT AUTO_INCREMENT PRIMARY KEY,
  first_name  VARCHAR(50) NOT NULL,
  last_name   VARCHAR(50) NOT NULL,
  email       VARCHAR(150) NOT NULL UNIQUE,
  phone       VARCHAR(30),
  certification VARCHAR(100),
  experience_years INT NOT NULL DEFAULT 0,
  hourly_fee  DECIMAL(8,2) NOT NULL DEFAULT 0,
  bio         TEXT
);

CREATE TABLE trainer_ground (
  trainer_id INT NOT NULL,
  ground_id  INT NOT NULL,
  PRIMARY KEY (trainer_id, ground_id),
  FOREIGN KEY (trainer_id) REFERENCES trainer(trainer_id),
  FOREIGN KEY (ground_id)  REFERENCES ground(ground_id)
);

CREATE TABLE player (
  player_id     INT AUTO_INCREMENT PRIMARY KEY,
  first_name    VARCHAR(50) NOT NULL,
  last_name     VARCHAR(50) NOT NULL,
  email         VARCHAR(150) NOT NULL UNIQUE,
  phone         VARCHAR(30),
  date_of_birth DATE,
  gender        ENUM('male','female','other'),
  skill_level   ENUM('beginner','intermediate','advanced','professional') NOT NULL DEFAULT 'beginner',
  group_type_id INT,
  location_id   INT,
  trainer_id    INT,
  joined_on     DATE NOT NULL DEFAULT (CURRENT_DATE),
  FOREIGN KEY (group_type_id) REFERENCES group_type(group_type_id),
  FOREIGN KEY (location_id)   REFERENCES location(location_id),
  FOREIGN KEY (trainer_id)    REFERENCES trainer(trainer_id)
);

-- Court availability: one row per court per time slot
CREATE TABLE court_availability (
  availability_id INT AUTO_INCREMENT PRIMARY KEY,
  court_id   INT NOT NULL,
  slot_date  DATE NOT NULL,
  start_time TIME NOT NULL,
  end_time   TIME NOT NULL,
  is_available BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE KEY uq_slot (court_id, slot_date, start_time),
  CHECK (end_time > start_time),
  FOREIGN KEY (court_id) REFERENCES court(court_id)
);

CREATE TABLE booking (
  booking_id      INT AUTO_INCREMENT PRIMARY KEY,
  availability_id INT NOT NULL UNIQUE,
  player_id       INT NOT NULL,
  trainer_id      INT,
  group_type_id   INT,
  booked_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (availability_id) REFERENCES court_availability(availability_id),
  FOREIGN KEY (player_id)       REFERENCES player(player_id),
  FOREIGN KEY (trainer_id)      REFERENCES trainer(trainer_id),
  FOREIGN KEY (group_type_id)   REFERENCES group_type(group_type_id)
);

-- Number of free courts per ground per slot
CREATE VIEW v_courts_available AS
SELECT g.ground_id, g.name AS ground_name, l.city,
       ca.slot_date, ca.start_time, ca.end_time,
       COUNT(*) AS available_courts
FROM court_availability ca
JOIN court c  ON c.court_id = ca.court_id AND c.status = 'active'
JOIN ground g ON g.ground_id = c.ground_id
JOIN location l ON l.location_id = g.location_id
WHERE ca.is_available = TRUE
GROUP BY g.ground_id, g.name, l.city, ca.slot_date, ca.start_time, ca.end_time;

-- Sample data
INSERT INTO location (name, address, city, state, postal_code) VALUES
  ('Downtown Sports Complex', '12 Main St', 'Austin', 'TX', '73301');
INSERT INTO ground (location_id, name, surface, total_courts, hourly_rate) VALUES
  (1, 'Arena A', 'wooden', 4, 20.00);
INSERT INTO court (ground_id, court_no) VALUES (1,1),(1,2),(1,3),(1,4);
INSERT INTO group_type (name, description, min_age, max_age) VALUES
  ('Junior','Under 16',6,15),('Adult','Adults',16,49),('Senior','50 and above',50,NULL),('Women','Women only',16,NULL);
INSERT INTO trainer (first_name,last_name,email,certification,experience_years,hourly_fee) VALUES
  ('Anil','Kumar','anil@example.com','BWF Level 2',8,35.00);
INSERT INTO trainer_ground VALUES (1,1);
INSERT INTO player (first_name,last_name,email,skill_level,group_type_id,location_id,trainer_id) VALUES
  ('Rahul','Sharma','rahul@example.com','intermediate',2,1,1);
INSERT INTO court_availability (court_id,slot_date,start_time,end_time) VALUES
  (1,'2026-11-01','18:00','19:00'),(2,'2026-11-01','18:00','19:00');
