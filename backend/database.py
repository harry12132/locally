"""SQLite storage for local client, invoice, and contract records."""

import os
import sqlite3
from pathlib import Path


DEFAULT_DATABASE_PATH = Path(__file__).with_name("firm_data.db")


def database_path() -> Path:
    return Path(os.environ.get("FIRM_DB_PATH", DEFAULT_DATABASE_PATH))


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(path or database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(path: str | Path | None = None) -> None:
    with connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id TEXT PRIMARY KEY,
                client_id INTEGER NOT NULL REFERENCES clients(id),
                status TEXT NOT NULL,
                amount REAL NOT NULL CHECK (amount >= 0),
                due_date TEXT
            );

            CREATE TABLE IF NOT EXISTS contracts (
                id INTEGER PRIMARY KEY,
                client_id INTEGER REFERENCES clients(id),
                title TEXT NOT NULL,
                content TEXT NOT NULL
            );

            INSERT OR IGNORE INTO clients (name) VALUES
                ('Smith & Co'), ('Acme Corp');

            INSERT OR IGNORE INTO invoices (id, client_id, status, amount, due_date)
                SELECT 'INV-102', id, 'OVERDUE', 4500.00, '2026-09-15'
                FROM clients WHERE name = 'Smith & Co';
            INSERT OR IGNORE INTO invoices (id, client_id, status, amount, due_date)
                SELECT 'INV-101', id, 'PAID', 1200.00, '2026-09-01'
                FROM clients WHERE name = 'Acme Corp';

            INSERT INTO contracts (client_id, title, content)
                SELECT id, 'Standard Services Agreement',
                    'Late payments incur 2% interest per 30 days overdue.'
                FROM clients WHERE name = 'Smith & Co'
                AND NOT EXISTS (
                    SELECT 1 FROM contracts WHERE title = 'Standard Services Agreement'
                );
            INSERT INTO contracts (client_id, title, content)
                SELECT id, 'Acme Consulting Terms',
                    'Either party may terminate this agreement with 30 days written notice.'
                FROM clients WHERE name = 'Acme Corp'
                AND NOT EXISTS (
                    SELECT 1 FROM contracts WHERE title = 'Acme Consulting Terms'
                );
            """
        )


def find_invoices(
    client_name: str, path: str | Path | None = None
) -> list[dict[str, object]]:
    with connect(path) as connection:
        rows = connection.execute(
            """
            SELECT clients.name AS client, invoices.id AS invoice_id,
                   invoices.status, invoices.amount, invoices.due_date
            FROM invoices
            JOIN clients ON clients.id = invoices.client_id
            WHERE clients.name = ? COLLATE NOCASE
            ORDER BY invoices.id
            """,
            (client_name.strip(),),
        ).fetchall()
    return [dict(row) for row in rows]


def search_contracts(query: str, path: str | Path | None = None) -> list[dict[str, object]]:
    terms = [term.strip(".,!?;:'\"()[]{}") for term in query.split()]
    terms = [term for term in terms if len(term) > 2]
    if not terms:
        return []

    matching_terms = " OR ".join(
        "(contracts.title LIKE ? OR contracts.content LIKE ?)" for _ in terms
    )
    parameters = tuple(value for term in terms for value in (f"%{term}%", f"%{term}%"))
    with connect(path) as connection:
        rows = connection.execute(
            f"""
            SELECT contracts.title, contracts.content, clients.name AS client
            FROM contracts
            LEFT JOIN clients ON clients.id = contracts.client_id
            WHERE {matching_terms}
            ORDER BY contracts.id
            LIMIT 10
            """,
            parameters,
        ).fetchall()
    return [dict(row) for row in rows]