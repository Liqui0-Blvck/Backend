#!/bin/bash
echo "Resetting PostgreSQL database..."
PGPASSWORD=fruitpos_pass psql -h localhost -p 5433 -U fruitpos_user -d fruitpos -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
echo "Database reset complete!"
