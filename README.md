# CampusBite 🍔
### Restaurant Ordering & Delivery Platform

CampusBite is a full-stack restaurant ordering and delivery platform designed to connect customers, restaurant owners, and delivery partners through a single application.

Customers can explore restaurants, browse menus, place food orders, and track deliveries. Restaurant owners can manage their menus and incoming orders, while delivery partners can manage their assigned deliveries.

The platform also integrates AI-powered order insights to help customers understand their ordering history and spending patterns.

**Project Status:** 🚧 Under Development

## 🎯 Project Objectives

- Build a functional full-stack restaurant ordering application.
- Implement secure authentication and role-based access control.
- Manage the complete food ordering and delivery lifecycle.
- Integrate AI-powered customer order insights.
- Develop a responsive and user-friendly interface.
- Apply software engineering practices including modular architecture, database management, API development, and containerization.

## 👥 User Roles

### 1. Customer
- Register and log in.
- Browse restaurants and food menus.
- Search and filter dishes by name and price.
- Add, update, and remove cart items.
- Place orders using dummy payment processing.
- Track orders and view order history.
- Cancel eligible orders.
- Submit ratings and reviews.
- Request returns and refunds.
- Access AI-powered order insights.

### 2. Restaurant Owner
- Manage restaurant menus and food availability.
- View and manage incoming orders.
- Accept orders and update preparation status.
- Assign delivery partners.
- View restaurant statistics.
- Filter and paginate orders.
- Manage customer return and refund requests.
- View reminders for orders requiring attention.

### 3. Delivery Partner
- View assigned deliveries.
- Access customer delivery details.
- Update delivery statuses.
- Mark orders as delivered.
- View delivery history.

## 🛠️ Technology Stack

| Component | Technology |
|---|---|
| Frontend | React.js |
| Language | JavaScript (ES6+) |
| Routing | React Router DOM |
| State Management | React Hooks |
| API Integration | Fetch API |
| Backend | Python, FastAPI |
| Validation | Pydantic |
| ORM | SQLAlchemy |
| Authentication | JWT, bcrypt |
| Database | PostgreSQL |
| AI Integration | OpenAI API |
| Containerization | Docker, Docker Compose |
| Version Control | Git, GitHub |

## ✨ Key Features

- Role-based authentication and authorization.
- Restaurant and menu management.
- Food discovery and filtering.
- Shopping cart and checkout.
- Dummy payment processing.
- Order lifecycle management.
- Delivery partner assignment and tracking.
- Customer reviews and ratings.
- Return and refund management.
- Separate dashboards for all three user roles.
- Dashboard statistics, filtering, and pagination.
- AI-powered order summaries and insights.
- API request logging and response-time monitoring.
- Background tasks for restaurant order reminders.
- Dockerized backend application.

## 🔄 Order Lifecycle

The application follows the following order lifecycle:

`PLACED → ACCEPTED → PREPARING → READY → ASSIGNED → OUT_FOR_DELIVERY → DELIVERED`

Additional statuses:

- `CANCELLED`
- `REFUNDED`

Order status transitions are validated by the backend according to user roles and business rules.

## 🧠 AI Integration

CampusBite integrates the OpenAI API to provide customers with insights based on their previous orders.

Example queries include:

- Summarize my last five orders.
- Which of my orders are still not delivered?
- How much did I spend this week?
- Which food items have I ordered most frequently?

AI requests use authenticated customer order history as context, ensuring that customers can only access their own information.

## 🏗️ Project Architecture

The application follows a modular full-stack architecture.

- **Frontend:** React.js application responsible for the user interface and client-side navigation.
- **Backend:** FastAPI application responsible for REST APIs, business logic, authentication, and authorization.
- **Database:** PostgreSQL for persistent relational data storage.
- **ORM:** SQLAlchemy for database models and operations.
- **AI Service:** OpenAI API for customer order insights.
- **Containerization:** Docker and Docker Compose for backend deployment and database connectivity.

## 📂 Project Structure

```text
campusbite/
│
├── frontend/
│   └── React application
│
├── backend/
│   ├── app/
│   │   ├── core/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── routers/
│   │   ├── services/
│   │   ├── dependencies/
│   │   ├── middleware/
│   │   └── tasks/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
│
├── docker-compose.yml
├── .gitignore
└── README.md
```

## 🚀 Getting Started

Installation and execution instructions will be added as the application architecture and development environment are established.

The completed project will include instructions for:

1. Setting up the React frontend.
2. Configuring the Python backend.
3. Setting up PostgreSQL.
4. Configuring environment variables.
5. Running the backend using Docker Compose.
6. Accessing the FastAPI API documentation.

## 🔐 Environment Configuration

Sensitive information must be stored in environment variables and must never be committed to the repository.

An `.env.example` file will document the required configuration variables without exposing actual credentials.

## 📚 API Documentation

The backend will provide interactive API documentation through FastAPI.

- Swagger UI: `/docs`
- ReDoc: `/redoc`

## 🗺️ Development Progress

CampusBite is being developed incrementally, with each milestone tracked through Git commits.

- [ ] Project setup and architecture
- [ ] Database configuration and models
- [ ] Authentication and role-based authorization
- [ ] Restaurant and menu management
- [ ] Food search and filtering
- [ ] Cart and checkout
- [ ] Dummy payment processing
- [ ] Order lifecycle management
- [ ] Delivery management
- [ ] Customer reviews and refunds
- [ ] Role-based dashboards
- [ ] AI-powered order insights
- [ ] Middleware and background tasks
- [ ] Docker configuration
- [ ] Testing and documentation

## 🔧 Version Control

Git and GitHub are used to track the development process and maintain a structured project history.

Development follows incremental commits representing actual implementation milestones.

## 📌 Project Information

| Detail | Information |
|---|---|
| Project | CampusBite |
| Type | Full-Stack Web Application |
| Program | Software Engineering with AI |
| Institution | Masai × E&ICT Academy, IIT Roorkee |
| Development Period | November 2026 |
| Submission Deadline | 15 November 2026 |

---

*CampusBite is an academic capstone project developed as part of the Software Engineering with AI certification program.*
