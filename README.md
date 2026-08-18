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

**Commands Reference**

**Container Lifecycle Management**
```
# Build the multi-stage image and start all containers in detached background mode
docker compose up --build -d

# Stop all running containers without deleting database storage volumes
docker compose down

# Stop all containers and completely wipe local PostgreSQL volumes (Full System Reset)
docker compose down -v

# View real-time aggregated system logs
docker compose logs -f
```
**Testing using pytest**
```
# Spin up a completely fresh, isolated container instance, run tests, and self-destruct
docker compose run --rm web pytest
```
**API Documentation** 
**Interactive Swagger UI API Documentation:**
```
**[http://localhost:8000/docs]**
**[http://localhost:8000/docs]**
```
