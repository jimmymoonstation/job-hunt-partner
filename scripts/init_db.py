#!/usr/bin/env python3
"""Initialize the database and create all tables."""
import sys
sys.path.insert(0, '/opt/job-hunt-partner')

from src.api.database import init_db
init_db()
print("Database initialized at /opt/job-hunt-partner/jobs.db")
