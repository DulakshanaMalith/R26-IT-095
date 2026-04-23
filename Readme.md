```markdown
# Intelligent Project Management System for Undergraduate Students

A comprehensive MERN and FastAPI stack application for managing undergraduate research projects, featuring intelligent team formation, feasibility analysis, and progress tracking.

## Features

- Intelligent Team Formation & Student Vector Profiling
- Topic Feasibility Analysis & Predictive Modeling
- Solution to the Academic "Cold Start" Problem
- Multi-Objective Optimization Engine
- Automated Progress Tracking & Risk Assessment
- Role-based Access Control (Admin, Supervisor, Student)
- Multi-service Architecture (Node.js Core + FastAPI Algorithms)

## Prerequisites

- Node.js (v18 or higher)
- Python (v3.9 or higher)
- MongoDB
- npm or yarn
- pip

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd intelligent-project-management
```

2. Install Node.js backend dependencies:
```bash
cd backend-node
npm install
```

3. Install FastAPI microservice dependencies:
```bash
cd ../backend-fastapi
pip install -r requirements.txt
```

4. Install frontend dependencies:
```bash
cd ../frontend
npm install
```

5. Create `.env` files:

In `backend-node/.env`:
```
PORT=5000
MONGODB_URI=your_mongodb_uri
JWT_SECRET=your_jwt_secret
FASTAPI_URL=http://localhost:8000
```

In `backend-fastapi/.env`:
```
PORT=8000
MODEL_PATH=./models/feasibility_model.pkl
```

## Running the Application

1. Start the Node.js backend server:
```bash
# From the backend-node directory
npm run dev
```

2. Start the FastAPI microservice:
```bash
# From the backend-fastapi directory
uvicorn main:app --reload
```

3. Start the frontend development server:
```bash
# From the frontend directory
npm run dev
```

The application will be available at:
- Frontend: http://localhost:5173
- Node API: http://localhost:5000
- FastAPI Docs: http://localhost:8000/docs

## Default Admin Account

Username: admin
Password: admin123

## API Documentation

### Authentication & Core (Node.js)
- POST /api/auth/login - Login user
- GET /api/auth/me - Get current user
- POST /api/students/profile - Update student skills and academic history
- GET /api/projects/status - Get current project timeline

### Intelligent Algorithms (FastAPI)
- POST /api/ml/vector-profile - Generate student vector representations
- POST /api/ml/optimize-teams - Run multi-objective team formation engine
- POST /api/ml/feasibility-score - Calculate success probability for a topic

## Team Formation & Topic Selection Process

1. **Student Vector Profiling**
   - Students register and input their academic history, technical skills (e.g., MERN, FastAPI), and research interests.
   - The system generates a multi-dimensional vector profile for each student.

2. **Topic Proposal & Feasibility Analysis**
   - Students or supervisors submit proposed research topics.
   - The FastAPI engine analyzes the required skills against the available student pool and historical success metrics to generate a Feasibility Score.

3. **Intelligent Matching**
   - The optimization engine groups students into balanced teams.
   - It ensures each team has the collective vector profile necessary to meet the technical demands of their assigned or chosen topic, bypassing the "Cold Start" problem.

## License

MIT
```
