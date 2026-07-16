# Storage and schema

Tests and demos use defensive in-memory storage. Durable use requires an explicit CLI command and standard-library SQLite under ignored `data/knowledge/`. Schema version 1 uses transactions, foreign keys, fixed migrations, parameterized SQL, and indexed topic/category fields.
