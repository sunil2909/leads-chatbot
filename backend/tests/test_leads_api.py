import unittest
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy import inspect as sqlalchemy_inspect
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from database import build_database_url
from main import app, get_session
from models import Lead
from seed_data import read_leads_csv


class LeadsApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(cls.engine)

    @classmethod
    def tearDownClass(cls):
        cls.engine.dispose()

    def setUp(self):
        with Session(self.engine) as session:
            session.add(Lead(lead_number=660737, lead_origin="API"))
            session.commit()

        def override_get_session():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_get_session
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        with Session(self.engine) as session:
            session.execute(delete(Lead))
            session.commit()

    def test_lists_leads_from_the_database(self):
        response = self.client.get("/api/leads")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["lead_number"], 660737)
        self.assertEqual(response.json()[0]["lead_origin"], "API")

    def test_reads_all_csv_rows_and_preserves_quoted_and_blank_values(self):
        csv_path = Path(__file__).parents[1] / "alembic" / "Leads.csv"

        leads = read_leads_csv(csv_path)
        leads_by_number = {lead["lead_number"]: lead for lead in leads}

        self.assertEqual(len(leads), 500)
        self.assertEqual(
            leads_by_number[660471]["specialization"],
            "Banking, Investment And Insurance",
        )
        self.assertIsNone(leads_by_number[660339]["specialization"])
        self.assertTrue(leads_by_number[660471]["converted"])

    def test_database_url_supports_reserved_password_characters(self):
        environment = {
            "POSTGRES_USER": "demo",
            "POSTGRES_PASSWORD": "p@ss:/?#%word",
            "DATABASE_HOST": "db",
            "DATABASE_PORT": "5432",
            "POSTGRES_DB": "leads_db",
        }
        with patch.dict(os.environ, environment, clear=True):
            database_url = build_database_url()

        self.assertEqual(database_url.password, "p@ss:/?#%word")
        self.assertEqual(database_url.host, "db")

    def test_initial_migration_seeds_and_downgrade_removes_the_table(self):
        backend_path = Path(__file__).parents[1]
        config_path = backend_path / "alembic.ini"

        with TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "migration.db"
            database_url = f"sqlite:///{database_path.as_posix()}"
            config = Config(str(config_path))

            with patch.dict(os.environ, {"DATABASE_URL": database_url}):
                command.upgrade(config, "head")
                migration_engine = create_engine(database_url)
                with migration_engine.connect() as connection:
                    seeded_count = connection.exec_driver_sql(
                        "SELECT COUNT(*) FROM leads"
                    ).scalar_one()
                self.assertEqual(seeded_count, 500)

                command.downgrade(config, "base")
                self.assertFalse(sqlalchemy_inspect(migration_engine).has_table("leads"))
                migration_engine.dispose()


if __name__ == "__main__":
    unittest.main()