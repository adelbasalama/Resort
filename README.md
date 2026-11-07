# ReSort · Assignment 3 · Flask and MySQL

**Group 8 · MDT · Waste Sorting & Recycling Assistant**

| Team member | Student ID | Subsystem |
| --- | --- | --- |
| Adel Abasalam Esmail Basalama | 7225969 | 1 |
| Mahdi Yahia | 7221528 | 2 |
| Jayesh Patil | 7225971 | 3 |
| Rashi Jain | 7225974 | 4 |

This submission is a read-only Flask API backed by MySQL 8.4. The [schema](ai-coach/sql/schema.sql) creates and seeds the `waste_assistant` database with a labeled Dortmund demo region and disposal rules. The [Flask endpoints](ai-coach/app/main.py) return JSON from the [MySQL repository](ai-coach/app/db.py).

## Start and verify

From the repository root in PowerShell with Docker running:

```powershell
docker compose -p resort-assignment3 -f ai-coach/docker-compose.yml up -d --build
(Invoke-RestMethod http://127.0.0.1:5000/v1/regions).regions
(Invoke-RestMethod 'http://127.0.0.1:5000/v1/rules?region_id=demo-dortmund').rules
```

Expect the region `Dortmund (demo rules)` and entries such as `beverage_can`. The API needs no OpenAI key. To compare the response with MySQL, open the database client and enter the development password from the [Compose file](ai-coach/docker-compose.yml).

```powershell
docker compose -p resort-assignment3 -f ai-coach/docker-compose.yml exec db mysql -u capstone -p waste_assistant
```

```sql
SELECT id, name, source_url FROM regions;
SELECT item_key, category, bin_label FROM recycling_rules WHERE region_id = 'demo-dortmund';
```

Stop the stack when finished:

```powershell
docker compose -p resort-assignment3 -f ai-coach/docker-compose.yml down
```

[GitHub submission branch](https://github.com/adelbasalama/Resort/tree/HomeworkAssignment3)
