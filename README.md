# Chat2DB - MySQL Chat Interface

A web application that allows users to interact with MySQL databases through a chat-like interface.

## Features

- Connect to MySQL databases with authentication
- Execute SQL queries with rich syntax highlighting
- View query results in a formatted table
- Support for database selection

## Setup and Installation

### Prerequisites

- Python 3.7+
- Node.js and npm
- MySQL server

### Backend Setup

1. Install Python dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root (optional):
   ```
   DB_HOST=localhost
   DB_USER=root
   DB_PASSWORD=your_password
   DB_PORT=3306
   ```

### Frontend Setup

1. Navigate to the `frontend` directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

### Running the Application

From the project root, run:

```
python run.py
```

This will start both the backend and frontend servers and open a browser window.

Alternatively, you can run them separately:

- Backend: `uvicorn backend.main:app --reload`
- Frontend: `cd frontend && npm run dev -- --open`

## Usage

1. Enter your MySQL server connection details
2. Click "Connect" to establish a connection
3. Select a database from the dropdown
4. Enter your SQL query in the editor
5. Click "Execute Query" to run the query and see results

## Technologies Used

- Backend: FastAPI, MySQL Connector
- Frontend: SvelteKit, HTMX, Monaco Editor
- UI: Tailwind CSS
