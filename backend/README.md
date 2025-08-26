# Strategy Hunter Backend

This is a backend application developed with the FastAPI framework, providing robust API support for the Strategy Hunter financial analysis tool. It handles core functionalities such as user authentication, trade journal management, financial market data integration, option chain analysis, and strategy volatility calculation.

## Key Features

- **User Authentication**: Provides a secure JWT (JSON Web Token) registration and login mechanism.
- **Trade Journal (CRUD)**: Allows users to create, read, update, and delete their trade records.
- **Market Data**: Fetches real-time and historical stock data from external APIs (e.g., Polygon.io).
- **Option Chain**: Provides option chain data for specific stocks and supports mock data for testing.
- **Volatility Calculation**: Built-in tools for calculating historical and implied volatility.
- **Strategy Management**: Allows users to save and manage their trading strategies.

## API Routes

The project's API routes are modularized by function for clarity and ease of understanding:

- `/auth`: Handles all user authentication-related operations, including registration, login, and retrieving the current user's information.
- `/journal`: Manages CRUD operations for the trade journal.
- `/market-data`: Provides market information such as stock quotes and historical data.
- `/options`: Retrieves option chain data for individual stocks.
- `/strategies`: Used for managing and analyzing trading strategies.
- `/volatility`: Provides volatility-related calculations and data queries.
- `/tools`: Offers some auxiliary tools or internal testing endpoints.

## Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Database**: [SQLModel](https://sqlmodel.tiangolo.com/), [SQLAlchemy](https://www.sqlalchemy.org/)
- **Database Driver**: [aiosqlite](https://github.com/omnilib/aiosqlite) (Asynchronous driver for SQLite)
- **Data Validation**: [Pydantic](https://pydantic-docs.helpmanual.io/)
- **Authentication**: [python-jose](https://github.com/mpdavis/python-jose) for JWT, [passlib](https://passlib.readthedocs.io/en/stable/) for hashing
- **Environment Variable Management**: [python-dotenv](https://github.com/theskumar/python-dotenv)
- **HTTP Client**: [httpx](https://www.python-httpx.org/)

## Local Installation and Startup

Follow the steps below to set up and run this project in your local environment.

### 1. Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) (A fast Python package installer and resolver)

You can install `uv` on macOS, Linux, or Windows:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Create Virtual Environment and Install Dependencies

`uv` can create a virtual environment and install dependencies from `requirements.txt` seamlessly.

In the project root directory:

```bash
# Create a virtual environment named .venv
uv venv

# Activate the environment and install dependencies
source .venv/bin/activate
uv pip install -r requirements.txt
```

For Windows, use `.venv\Scripts\activate` to activate.

### 3. Configure Environment Variables

Copy or rename `.env.example` (if it exists) to `.env`, and fill in the necessary environment variables. If there is no example file, create the `.env` file manually.

```env
# .env

# API key for connecting to Polygon.io
POLYGON_API_KEY="YOUR_POLYGON_API_KEY"

# Secret key for JWT signing, please replace with a complex and random string
SECRET_KEY="your_super_secret_key_for_jwt"

# JWT signing algorithm
ALGORITHM="HS256"

# Access Token expiration time (in minutes)
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 5. Run Database Migrations

The application will automatically create database tables using SQLModel upon startup.

### 6. Start the Application

Use `uvicorn` to start the FastAPI application. The `--reload` parameter will cause the server to restart automatically when code changes, which is ideal for a development environment.

```bash
uvicorn app.main:app --reload
```

After the server starts, you can open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser to view it.
The interactive API documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Testing

This project uses `pytest` for testing. The tests are located in the `tests/` directory and are designed to verify the functionality of each API endpoint.

### Running Tests

Before running the tests, make sure you have activated the virtual environment and installed all dependencies (including development dependencies).

To run all tests, execute the following command in the `backend` directory:

```bash
pytest
```

This will automatically discover and run all test cases in the `tests/` directory.
