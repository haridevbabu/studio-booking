# studio-booking
A backend for boutique fitness studios. Studios sell credit packs. Members spend credits to book classes. Classes have a limited number of spots, cancellation rules, and a waitlist

Project structure
```
studio-booking-app/
├── .github/
│   └── workflows/
│       └── ci.yml             # GitHub Actions continuous integration pipeline
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI routes, lifespan handling & Idempotency Key Gateway
│   ├── models.py              # SQLAlchemy 2.0 ORM data layer tables & relations
│   ├── schemas.py             # schemas
│   ├── services.py            # Business Logics
│   ├── auth.py                #  Header-based authorization
│   └── database.py            # Async engine pooling configurations (`AsyncSessionLocal`)
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # In-memory SQLite initialization
│   └── test_booking.py        # tests for the workflow using pytest
├── docker-compose.yml         # Container definitions routing PostgreSQL and FastAPI
├── Dockerfile                 # Containerization
├── pyproject.toml             # config for ruff and mypy for lint and type checking
├── pytest.ini                 # Testing directions for coverage
└── requirements.txt           # dependencies list
```
