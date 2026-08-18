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
## Workflow

Follow these steps to build the application, run code checks, and test the API workflow.

1. Build and Run the App
```
docker compose up --build -d
```
Note: Run docker compose ps to check the health of containers

2. Run Code Quality Checks
```
# Code linter check
docker compose exec web ruff check .

# Static type check
docker compose exec web mypy .
```

3. Run the Test Suite

```
docker compose run --rm web pytest
```

 4. Swagger interactive Api docs
Open your browser and navigate to the interactive Swagger UI panel:
**[http://localhost:8000/docs](http://localhost:8000/docs)**

Execute the following sequential requests to test the core business rules:

1. **Create Users (`POST /users`)**
   - Create a staff user (`"is_staff": true`).
   - Create a normal member (`"is_staff": false`).
   - *Action*: Copy the unique `id` UUID values returned for both profiles.

2. **Setup Studio (`POST /studios`)**
   - Create a studio profile (e.g., `name: "new_studio"`, `timezone: "Asia/Kolkata"`).
   - *Action*: Add the staff UUID token into the `X-User-Id` request header field.

3. **Schedule Class (`POST /studios/{studio_id}/classes`)**
   - Add a fitness class with a specific price cost (e.g., `credit_cost: 2`).
   - *Action*: Use the staff UUID token inside the `X-User-Id` request header field.

4. **Grant Pack (`POST /users/{user_id}/credit-packs`)**
   - Add a spendable pack of credits (e.g., `total_credits: 10`) onto the member profile.
   - *Action*: Use the staff UUID token inside the `X-User-Id` request header field.

5. **Book a Spot (`POST /bookings`)**
   - Book the class using the member's UUID token inside the `X-User-Id` header.
   - Provide an arbitrary string value (e.g., `token-123`) inside the `Idempotency-Key` header field.
   - *Action*: Click execute a second time with the identical key string to confirm the gateway catches the duplicate retry and skips processing charges twice.

6. **Check Credit Balance (`GET /users/{user_id}/credits/balance`)**
   - Check the member's live remaining balance or pass a past date string to `point_in_time`.
   - *Action*: Confirm the live balance decreased from `10` down to `8` tokens.

7. **List User Bookings (`GET /users/{user_id}/bookings`)**
   - View all current reservation lifecycles for the member profile.
   - *Action*: Verify the target booking displays an active `CONFIRMED` status flag.

8. **Audit Statements (`GET /users/{user_id}/credits/statement`)**
   - Open the immutable audit logs for the member profile.
   - *Action*: Verify it tracks every movement precisely: a positive grant entry (`+10`) and a negative deduction entry (`-2`).

9. **Cancel Booking (`DELETE /bookings/{reservation_id}`)**
   - Cancel the allocation using the member's UUID token inside the `X-User-Id` header.
   - *Action*: Verify credits are refunded if done before the 4-hour local cutoff, or forfeited if done late. Duplicate cancellation clicks will be blocked automatically.



