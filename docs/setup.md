# Installation & Setup Guide

This guide provides step-by-step setup instructions for running the **Secure AI Assistant for Legal Data Analysis** on Windows, Linux, or macOS.

---

## 1. Prerequisites

- **Python**: `3.10+` (Tested on Python 3.13)
- **Node.js**: `v18+` or `v20+` (Tested on Node.js v24)
- **npm**: `v9+` (Tested on npm 11)

---

## 2. Step-by-Step Backend Setup (FastAPI)

1. Open a terminal and navigate to the backend directory:
   ```bash
   cd secure-legal-ai/backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv

   # Windows (PowerShell):
   .\venv\Scripts\Activate.ps1

   # Linux/macOS:
   source venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Create `.env` file from template:
   ```bash
   cp .env.example .env
   ```

5. Start the FastAPI backend server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

6. Verify backend server is running:
   - Interactive Swagger API Documentation: `http://127.0.0.1:8000/docs`
   - Health Check API: `http://127.0.0.1:8000/api/v1/health`

---

## 3. Step-by-Step Frontend Setup (React + Vite + Tailwind CSS)

1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd secure-legal-ai/frontend
   ```

2. Create `.env` file from template:
   ```bash
   cp .env.example .env
   ```

3. Install Node.js dependencies:
   ```bash
   npm install
   ```

4. Start the frontend development server:
   ```bash
   npm run dev
   ```

5. Access the application in your web browser:
   - URL: `http://localhost:5173`

---

## 4. Running Automated Pytest Suite

To execute all 95 automated security, RBAC, vector retrieval, and pipeline tests:

```bash
cd secure-legal-ai
python -m pytest
```
