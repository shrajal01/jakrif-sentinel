<div align="center">

# ⚡ JakRif Sentinel

### A Fault-Tolerant Payment Reliability & Observability Platform

*A backend playground that treats payment failures as the default case — not the exception.*

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-async-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![RabbitMQ](https://img.shields.io/badge/RabbitMQ-3--management-FF6600?style=for-the-badge&logo=rabbitmq&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-idempotency-DC382D?style=for-the-badge&logo=redis&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=for-the-badge&logo=next.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)

[Problem](#-problem-statement) · [Architecture](#-system-architecture) · [Features](#-features) · [API Docs](#-api-documentation) · [Getting Started](#-getting-started) · [Resume Highlights](#-resume-highlights)

</div>

---

## 📖 Table of Contents

- [Problem Statement](#-problem-statement)
- [Why This Project Exists](#-why-this-project-exists)
- [System Architecture](#-system-architecture)
- [Complete Project Flow](#-complete-project-flow)
- [Payment Lifecycle — Sequence Diagram](#-payment-lifecycle--sequence-diagram)
- [Retry & Fault-Tolerance Workflow](#-retry--fault-tolerance-workflow)
- [Tech Stack](#-tech-stack)
- [Folder Structure](#-folder-structure)
- [Features](#-features)
- [Failure Scenarios Handled](#-failure-scenarios-handled)
- [Idempotency](#-idempotency)
- [Retry Mechanism](#-retry-mechanism)
- [Dead Letter Queue (DLQ)](#-dead-letter-queue-dlq)
- [Observability](#-observability)
- [Dashboard](#-dashboard)
- [API Documentation](#-api-documentation)
- [Getting Started](#-getting-started)
- [Example API Request & Response](#-example-api-request--response)
- [Screenshots](#-screenshots)
- [Future Improvements](#-future-improvements)
- [Resume Highlights](#-resume-highlights)
- [Lessons Learned](#-lessons-learned)
- [License](#-license)

---

## 🎯 Problem Statement

Every real payment system eventually talks to something it doesn't control — a bank, a card network, a third-party processor. That dependency **will** time out, return `500`, respond twice for the same request, or simply vanish mid-transaction. Most side projects skip this reality and only implement the happy path: `POST /payments → 200 OK`.

**JakRif Sentinel deliberately does the opposite.** It ships with a *Fake Bank* whose failure modes are configurable, and builds the entire backend around the assumption that the bank call **will** fail — so the system has to survive timeouts, duplicate requests, poison messages, and partial failures without losing money, double-charging, or crashing the worker.

## 💡 Why This Project Exists

This repository is a hands-on exploration of the reliability patterns used in real fintech backends, implemented end-to-end rather than described in theory:

- **Idempotency** — safe request retries without double-processing
- **Asynchronous, queue-based processing** — decoupling API latency from downstream bank latency
- **Exponential backoff with jitter** — retrying transient failures without hammering a struggling dependency
- **Dead-lettering** — guaranteeing a worker can never get stuck in an infinite crash loop
- **Correlation-ID tracing** — following a single payment across an HTTP request and an asynchronous worker process
- **Live observability** — a real dashboard, not just log files, showing the system healing itself in real time

---

## 🏗 System Architecture

JakRif Sentinel is composed of four independently runnable processes that communicate through PostgreSQL, Redis, and RabbitMQ:

| Component | Responsibility |
|---|---|
| **API (`app/`)** | FastAPI service — creates payments, exposes auth, serves dashboard/monitoring endpoints |
| **Worker (`worker/`)** | Standalone `aio-pika` consumer — processes payments, talks to the Fake Bank, runs the retry engine |
| **Dashboard (`dashboard/`)** | Next.js 14 + TypeScript UI — polls the API every 5s for a live view of payments, retries, and infra health |
| **Fake Bank (`app/services/fake_bank.py`)** | In-process simulator with tunable success/failure/timeout/500/duplicate probabilities |

### High-Level Architecture Diagram

```mermaid
flowchart LR
    C["Client / Merchant App"] -->|HTTP| API

    subgraph API["FastAPI Service (app/)"]
        A1["POST /payments"]
        A2["GET /payments"]
        A3["/auth/*"]
        A4["/dashboard/*"]
    end

    subgraph DATA["Data Layer"]
        PG[("PostgreSQL")]
        RD[("Redis")]
    end

    subgraph BROKER["RabbitMQ"]
        EX{{"payments_exchange (direct)"}}
        Q1[["payments_queue"]]
        Q2[["payments_retry_queue"]]
        Q3[["payments_dead_letter_queue"]]
    end

    subgraph WORKER["Worker Process (worker/)"]
        W1["Main Consumer<br/>prefetch=1"]
        W2["Retry Consumer<br/>prefetch=100"]
        FB(("Fake Bank<br/>Simulator"))
    end

    D1["Next.js Dashboard<br/>(polls every 5s)"]

    A1 -->|"idempotency GET/SET NX lock"| RD
    A1 -->|"INSERT status=CREATED"| PG
    A1 -->|publish event| EX
    EX -->|"routing key: payment.process"| Q1
    Q1 --> W1
    W1 -->|"UPDATE status"| PG
    W1 -->|"process_transaction()"| FB
    FB -->|"SUCCESS / FAILED"| W1
    FB -.->|"Timeout / HTTP 500"| W1
    W1 -.->|recoverable error| Q2
    Q2 --> W2
    W2 -.->|"sleep(delay) then re-publish"| EX
    W1 -.->|"max retries / malformed / DB error"| Q3

    D1 -->|poll| A4
    A4 --> PG
    A4 -.->|passive queue declare| BROKER
    A4 -.->|PING| RD
```

---

## 🔄 Complete Project Flow

1. A client sends `POST /payments`, optionally with an `Idempotency-Key` header.
2. The API checks Redis for a cached response under that key. A hit returns the original response immediately — no new payment is created.
3. On a cache miss, the API acquires a short-lived Redis lock (`SET NX`, 30s TTL) so concurrent identical requests can't race each other.
4. A `Payment` row is inserted into PostgreSQL with status `CREATED` and a server-generated UUID.
5. A JSON event (including a `correlation_id`) is published to the `payments_exchange` direct exchange, routed to `payments_queue`.
6. The successful response is cached in Redis for 24h under the idempotency key, and the lock is released.
7. The API immediately returns `201 Created` to the client — the caller never waits on the bank call.
8. The **Worker** consumes the message, transitions the payment `ENQUEUED → PROCESSING`, and calls the Fake Bank.
9. On success or a business-level decline, the payment is marked `SUCCESS`/`FAILED` and the message is acknowledged.
10. On a **recoverable** error (timeout or HTTP 500), the message is routed to the retry engine with an exponential backoff delay — or to the Dead Letter Queue if 3 retries are already exhausted.
11. Every recoverable failure, retry, and dead-lettered message is persisted as a `RetryAttempt` row; every HTTP request is persisted as a `RequestLog` row — both power the dashboard.
12. The Next.js dashboard polls `/dashboard/*` every 5 seconds and renders payments, retries, and infrastructure health in real time.

---

## 🔁 Payment Lifecycle — Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant API as FastAPI (/payments)
    participant Redis
    participant Postgres
    participant Broker as RabbitMQ
    participant Worker
    participant Bank as Fake Bank

    Client->>API: POST /payments (Idempotency-Key)
    API->>Redis: GET idempotency:payments:{key}

    alt Cache hit
        Redis-->>API: cached payment response
        API-->>Client: 201 Created (deduplicated)
    else Cache miss
        API->>Redis: SET NX lock (30s TTL)
        API->>Postgres: INSERT payment (status=CREATED)
        Postgres-->>API: payment row
        API->>Broker: publish payment.process event
        API->>Redis: cache response (TTL 24h)
        API->>Redis: DEL lock
        API-->>Client: 201 Created

        Broker->>Worker: deliver message
        Worker->>Postgres: status = ENQUEUED
        Worker->>Postgres: status = PROCESSING
        Worker->>Bank: process_transaction()

        alt Success or business decline
            Bank-->>Worker: SUCCESS / FAILED
            Worker->>Postgres: status = SUCCESS / FAILED
            Worker->>Broker: ack message
        else Recoverable error (timeout / HTTP 500)
            Bank-->>Worker: FakeBankTimeoutError / FakeBankServerError
            Worker->>Postgres: persist RetryAttempt
            Worker->>Broker: publish to payments_retry_queue
            Worker->>Broker: ack original message
        end
    end
```

---

## ♻️ Retry & Fault-Tolerance Workflow

```mermaid
flowchart TD
    A["Message delivered from payments_queue"] --> B{"retry_count == 0?"}
    B -->|Yes, first attempt| C["status: ENQUEUED → PROCESSING"]
    B -->|No, this is a retry| D["Continue from existing PROCESSING state"]
    C --> E["Call Fake Bank"]
    D --> E
    E --> F{Result}
    F -->|SUCCESS| G["status = SUCCESS · ack"]
    F -->|Business FAILED| H["status = FAILED · ack"]
    F -->|"Timeout / HTTP 500"| I{"retry_count >= 3?"}

    I -->|No| J["retry_count += 1"]
    J --> K["delay = 5 × 2^retry_count + jitter(0–2s)"]
    K --> L["publish to payments_retry_queue"]
    L --> M["persist RetryAttempt: RETRY_SCHEDULED"]
    M --> N["ack original message"]
    N --> O["Retry consumer sleeps for 'delay' seconds"]
    O --> P["Re-publish to payments_exchange"]
    P --> A

    I -->|"Yes, 3 retries used"| Q["publish to payments_dead_letter_queue"]
    Q --> R["status = FAILED"]
    R --> S["persist RetryAttempt: DEAD_LETTER"]
    S --> T["ack original message (never requeued)"]
```

> Malformed messages, messages missing a `payment_id`, and invalid database state transitions **skip retries entirely** and are dead-lettered immediately with `message.reject(requeue=False)` — this is what stops a single bad message from looping forever (a "poison pill").

---

## 🧰 Tech Stack

**Backend / API**
- [FastAPI](https://fastapi.tiangolo.com/) 0.116 (async), Uvicorn
- [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (async + sync engines) with `psycopg[binary]` 3
- [Alembic](https://alembic.sqlalchemy.org/) for schema migrations
- [Pydantic v2](https://docs.pydantic.dev/) / `pydantic-settings` for config & validation
- [structlog](https://www.structlog.org/) for structured JSON logging

**Messaging & Caching**
- [RabbitMQ](https://www.rabbitmq.com/) via `aio-pika` (async AMQP client)
- [Redis](https://redis.io/) via `redis.asyncio` — idempotency cache + distributed locking

**Auth**
- `python-jose` for JWT signing/verification
- `passlib[bcrypt]` for password hashing

**Frontend (Observability Dashboard)**
- [Next.js 14](https://nextjs.org/) (App Router) + React 18 + TypeScript
- Tailwind CSS + `lucide-react` icons

**Infra**
- Docker / Docker Compose (RabbitMQ), PostgreSQL, Redis

---

## 📂 Folder Structure

```
jakrif-sentinel/
├── app/
│   ├── api/
│   │   ├── auth.py            # /auth/register, /auth/login, /auth/me
│   │   ├── dashboard.py       # /dashboard/* monitoring endpoints
│   │   ├── payments.py        # /payments CRUD + idempotency header
│   │   └── router.py          # root API router (aggregation point)
│   ├── core/
│   │   ├── config.py          # Pydantic settings (DB, JWT, RabbitMQ, Redis)
│   │   ├── context.py         # contextvars: request_id, correlation_id, payment_id, worker_id
│   │   ├── logging.py         # structlog configuration
│   │   ├── middleware.py      # RequestContextMiddleware + RequestLog persistence
│   │   └── security.py        # password hashing, JWT create/decode
│   ├── database/
│   │   ├── base.py            # SQLAlchemy DeclarativeBase
│   │   └── session.py         # sync + async engines/sessions, get_db()
│   ├── models/                # Payment, User, Service, RequestLog,
│   │                           # RetryAttempt, CircuitBreaker, HealthSnapshot
│   ├── repositories/          # scaffolded for future repository pattern
│   ├── schemas/                # Pydantic request/response models
│   ├── services/
│   │   ├── auth_service.py    # register/login/current-user logic
│   │   ├── fake_bank.py       # configurable bank failure simulator
│   │   ├── payment_service.py # idempotency, payment CRUD, state machine
│   │   ├── redis_service.py   # async Redis client wrapper
│   │   └── service_registry.py# lazy Service row creation for FK anchors
│   ├── utils/                  # scaffolded utilities
│   └── main.py                 # FastAPI app, lifespan, router mounting
├── worker/
│   ├── config.py               # worker-specific settings (RabbitMQ, queue names)
│   ├── consumer.py             # main + retry consumers, retry/DLQ logic
│   ├── main.py                 # worker process entrypoint
│   └── publisher.py            # RabbitMQ publisher (exchange + direct queue)
├── dashboard/                   # Next.js 14 observability UI
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx             # main dashboard (stats, timeline, logs)
│   │   ├── error.tsx / loading.tsx
│   │   └── globals.css
│   ├── package.json
│   └── tailwind.config.ts
├── migrations/                   # Alembic migration scripts
│   └── versions/
├── docker-compose.yml             # RabbitMQ (3-management) container
├── alembic.ini
├── requirements.txt
├── test_fake_bank.py               # manual Fake Bank sanity script
├── test_logging.py                 # manual structlog sanity script
├── start_rabbitmq.bat              # Windows helper: docker run rabbitmq
├── start_worker.bat                # Windows helper: python -m worker.main
└── .env.example
```

---

## ✨ Features

- ✅ **Idempotent payment creation** via `Idempotency-Key` header + Redis distributed lock
- ✅ **Event-driven processing** — API and Worker are fully decoupled through RabbitMQ
- ✅ **Exponential backoff retry engine** with jitter, isolated on its own queue and channel
- ✅ **Dead Letter Queue** for exhausted retries, poison messages, and DB/state errors
- ✅ **Configurable Fake Bank** simulating timeouts, HTTP 500s, duplicates, declines, and successes
- ✅ **Explicit payment state machine** (`CREATED → ENQUEUED → PROCESSING → SUCCESS/FAILED`) with guarded transitions
- ✅ **Structured JSON logging** with automatic `request_id` / `correlation_id` / `payment_id` / `worker_id` injection
- ✅ **Correlation-ID propagation** from the HTTP request all the way through the async worker
- ✅ **Fire-and-forget request logging** — `RequestLog` rows are persisted via `asyncio.create_task`, adding zero latency to the response
- ✅ **Live observability dashboard** built in Next.js, polling every 5 seconds
- ✅ **JWT authentication module** — register, login, and `me` endpoints with bcrypt hashing
- ✅ **Alembic-managed relational schema** across payments, users, services, logs, and retry attempts

---

## 🧯 Failure Scenarios Handled

| Scenario | How it's handled |
|---|---|
| Bank connection timeout | Caught as `FakeBankTimeoutError`, routed into the retry engine |
| Bank HTTP 500 | Caught as `FakeBankServerError`, routed into the retry engine |
| Duplicate request with same `Idempotency-Key` | Served from the Redis cache — no duplicate row, no duplicate bank call |
| Concurrent identical requests (same key, same instant) | Redis `SET NX` lock; the losing request waits 0.5s then re-checks the cache, or receives `409 Conflict` |
| Redis unavailable during idempotency check | Logged as a warning; the request still processes normally without idempotency protection |
| Malformed / unparsable RabbitMQ message | Rejected without requeue, routed straight to the DLQ |
| Message missing `payment_id` | Rejected without requeue, routed straight to the DLQ |
| Retries exhausted (3 attempts) | Routed to the DLQ, payment marked `FAILED` |
| Invalid DB state transition / unknown payment UUID | `ValueError` caught, message DLQ'd — **not** requeued (prevents an infinite loop) |
| Unexpected DB/connection failure mid-processing | Caught at the top level, DLQ'd, worker keeps running |
| Any uncaught exception inside the message handler | Outer `try/except` guarantees the worker process can never crash from a single bad message |

---

## 🔑 Idempotency

`POST /payments` accepts an optional `Idempotency-Key` header. The flow, exactly as implemented in `payment_service.create_payment`:

1. **Check cache** — `GET idempotency:payments:{key}` in Redis. A hit returns the previously created payment, byte-for-byte, without touching PostgreSQL or RabbitMQ again.
2. **Acquire lock** — if it's a cache miss, attempt `SET idempotency:payments:lock:{key} NX EX 30`.
3. **Lock contention** — if another request already holds the lock, the current request sleeps `0.5s` and re-checks the cache. If the in-flight request finished in that window, its result is returned; otherwise the second request receives **`409 Conflict`** rather than creating a duplicate payment.
4. **Process normally** — create the `Payment` row, publish the RabbitMQ event, and cache the response for **24 hours**.
5. **Always release the lock** — the lock is deleted in a `finally` block so a crash mid-request never permanently blocks future retries of the same key.
6. **Graceful degradation** — if Redis itself is unreachable, the exception is caught, a warning is logged, and the payment is still created without idempotency protection rather than failing the request outright.

---

## 🔂 Retry Mechanism

Recoverable bank failures (`FakeBankTimeoutError`, `FakeBankServerError`) are retried with **exponential backoff + jitter**, capped at **3 attempts**, before the payment is dead-lettered:

```
delay = 5 × 2^retry_count + random(0, 2) seconds
```

| Attempt | `retry_count` at failure | Delay formula | Approx. delay |
|---|---|---|---|
| 1st retry | 0 | 5 × 2⁰ + jitter | ~5–7s |
| 2nd retry | 1 | 5 × 2¹ + jitter | ~10–12s |
| 3rd retry | 2 | 5 × 2² + jitter | ~20–22s |
| Exhausted | 3 | — | routed to the Dead Letter Queue |

Two implementation details that keep this resilient:

- **Retry state lives in the message**, not in process memory — `retry_count` and `retry_delay` are embedded in the RabbitMQ payload, so the retry consumer is fully stateless and safe to restart.
- **The retry queue runs on its own channel** with `prefetch_count=100` (versus `1` on the main queue). A handful of messages sleeping through their backoff delay never blocks or starves the main payment queue.

---

## ☠️ Dead Letter Queue (DLQ)

Messages are published to `payments_dead_letter_queue` — with a `dlq_reason` field explaining why — whenever:

- The message body can't be parsed as JSON
- The message is missing a `payment_id`
- The payment has exhausted all 3 retries against the Fake Bank
- A database state-transition error occurs (invalid transition or unknown UUID)
- An unexpected exception occurs while updating the database
- The retry engine itself fails to re-publish a delayed message
- Any uncaught exception reaches the outermost handler

In every case the original message is explicitly rejected with **`requeue=False`**, so RabbitMQ never redelivers it to the same queue — this is the mechanism that prevents a single malformed or permanently failing message from looping the worker forever (a "poison pill"). DLQ messages are currently inspectable via the RabbitMQ Management UI; automated replay tooling is listed under [Future Improvements](#-future-improvements).

---

## 📊 Observability

- **Structured JSON logs** everywhere, via `structlog`, configured once in `configure_structlog()` and shared by both the API and the worker.
- **Context propagation** — `contextvars` (`request_id`, `correlation_id`, `payment_id`, `worker_id`) are injected into *every* log line automatically, without passing them explicitly through function signatures.
- **End-to-end correlation** — `RequestContextMiddleware` reads or generates `X-Request-ID` / `X-Correlation-ID` on every HTTP request, echoes them back in the response headers, and the `correlation_id` is carried inside the RabbitMQ payload so the worker's logs for that payment can be traced back to the exact API request that created it.
- **Zero-latency request logging** — each request is persisted as a `RequestLog` row via `asyncio.create_task`, in its own DB session, *after* the response has already been sent to the client.
- **Retry telemetry** — every recoverable bank-call failure is persisted as a `RetryAttempt` row (`RETRY_SCHEDULED` or `DEAD_LETTER`) with latency and error message, independent of the plain-text logs.
- **Service registry** — the API and worker lazily register themselves as `Service` rows (`jakrif-api`, `jakrif-worker`) that `RequestLog` and `RetryAttempt` foreign-key against, cached in-process after first lookup.
- **Aggregated health check** (`GET /dashboard/stats`) — pings PostgreSQL (`SELECT 1`), Redis (`PING`), and RabbitMQ (passive queue declaration for depth + reachability) and rolls them into a single `healthy` / `degraded` status.
- **Forward-looking schema** — `CircuitBreaker` and `HealthSnapshot` tables already exist in the migrations and models, ready to be wired into a live circuit-breaker and scheduled health poller without another schema change.

---

## 🖥 Dashboard

The `dashboard/` app is a standalone Next.js 14 + TypeScript client that polls the FastAPI `/dashboard/*` endpoints every **5 seconds** and renders:

- **Stat cards** — total payments, successful, failed (with live DLQ count), and processing (with live retry-queue depth)
- **Infrastructure health strip** — RabbitMQ, Redis, and PostgreSQL, each with a live healthy/degraded badge
- **Payment Timeline** — a live-updating feed of recent payments with status pills and click-to-copy correlation/trace IDs
- **Faults & Retries panel** — retry attempts (with the recorded error message) and terminal failures, side by side
- **Recent System Logs** — method, path, status code, and latency for recent HTTP requests, each linked to its `request_id`

It's a dark, glassmorphism-styled UI (Tailwind CSS + `lucide-react`) — built to make retries and dead-letters *visible*, not just logged.

---

## 📚 API Documentation

Interactive OpenAPI docs are auto-generated by FastAPI and available once the API is running:

- Swagger UI → `http://localhost:8000/docs`
- ReDoc → `http://localhost:8000/redoc`

<details>
<summary><strong>Endpoint reference</strong></summary>

**Health**

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check |

**Payments**

| Method | Path | Description |
|---|---|---|
| `POST` | `/payments` | Create a payment. Accepts an optional `Idempotency-Key` header |
| `GET` | `/payments` | List payments (`skip`, `limit` query params) |
| `GET` | `/payments/{payment_id}` | Get a single payment by internal integer ID |

**Auth**

| Method | Path | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new user |
| `POST` | `/auth/login` | OAuth2 password flow — returns a JWT. ⚠️ The form's `username` field must contain the account's **email**, since authentication is performed against email internally |
| `GET` | `/auth/me` | Return the currently authenticated user (Bearer token) |

**Dashboard**

| Method | Path | Description |
|---|---|---|
| `GET` | `/dashboard/stats` | Aggregate counts + live RabbitMQ/Redis/PostgreSQL health |
| `GET` | `/dashboard/recent-payments` | Most recent payments |
| `GET` | `/dashboard/failed-payments` | Most recent terminally failed payments |
| `GET` | `/dashboard/recent-retries` | Most recent retry attempts |
| `GET` | `/dashboard/recent-logs` | Most recent HTTP request logs |

> **Note:** the payments and dashboard endpoints are not currently gated behind the JWT auth module — see [Future Improvements](#-future-improvements).

</details>

---

## 🚀 Getting Started

### Prerequisites

- Python **3.11+**
- Node.js **18+** (for the dashboard)
- Docker (for RabbitMQ — see below)
- A running **PostgreSQL** instance
- A running **Redis** instance

> The provided `docker-compose.yml` only containerizes **RabbitMQ**. PostgreSQL and Redis are expected to be running separately (local install, your own Docker containers, or a managed service).

### 1. Clone & install

```bash
git clone https://github.com/shrajal01/jakrif-sentinel.git
cd jakrif-sentinel

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Variables

Copy `.env.example` to `.env`. Note that `app/core/config.py` **requires** `DATABASE_URL` and `SECRET_KEY` with no defaults — the API (and, because the worker imports the same config chain, the **worker too**) will fail to start without them.

| Variable | Required | Default | Description |
|---|:---:|---|---|
| `DATABASE_URL` | ✅ | — | PostgreSQL connection string |
| `SECRET_KEY` | ✅ | — | Secret used to sign JWTs |
| `ALGORITHM` | ❌ | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ | `30` | JWT access token lifetime |
| `RABBITMQ_HOST` | ❌ | `localhost` | RabbitMQ host |
| `RABBITMQ_PORT` | ❌ | `5672` | RabbitMQ port |
| `RABBITMQ_USER` | ❌ | `guest` | RabbitMQ username |
| `RABBITMQ_PASSWORD` | ❌ | `guest` | RabbitMQ password |
| `RABBITMQ_URL` | ❌ | `amqp://guest:guest@localhost:5672/` | Full AMQP URL used by API & worker |
| `REDIS_URL` | ❌ | `redis://localhost:6379/0` | Redis connection string |

```dotenv
# .env
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/jakrif_sentinel
SECRET_KEY=change-me-to-a-long-random-string

RABBITMQ_HOST=localhost
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

REDIS_URL=redis://localhost:6379/0
```

### 3. Docker Setup (RabbitMQ)

```bash
docker compose up -d
```

This starts `rabbitmq:3-management`, exposing:
- **AMQP** on `5672`
- **Management UI** on [`http://localhost:15672`](http://localhost:15672) (`guest` / `guest`)

On Windows, `start_rabbitmq.bat` does the equivalent via `docker run`.

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Running Locally

Run each process in its own terminal:

```bash
# Terminal 1 — API
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Worker (consumes RabbitMQ, talks to the Fake Bank, runs retries)
python -m worker.main          # Windows: start_worker.bat

# Terminal 3 — Dashboard
cd dashboard
npm install
npm run dev
```

| Service | URL |
|---|---|
| API + Swagger docs | `http://localhost:8000/docs` |
| Dashboard | `http://localhost:3000` |
| RabbitMQ Management | `http://localhost:15672` |

---

## 🧪 Example API Request & Response

**Create a payment**

```bash
curl -X POST http://localhost:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: 9c1b6e2a-2f7a-4e3a-8e35-3c2f0a2c9d10" \
  -d '{
        "amount": 250.00,
        "currency": "USD",
        "merchant_reference": "ORDER-1042",
        "description": "Subscription renewal"
      }'
```

```json
{
  "id": 1,
  "payment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "amount": 250.00,
  "currency": "USD",
  "status": "CREATED",
  "merchant_reference": "ORDER-1042",
  "description": "Subscription renewal",
  "created_at": "2026-07-16T10:15:00.123Z",
  "updated_at": null
}
```

Re-sending the exact same request with the same `Idempotency-Key` returns the identical response above — no second row is created, and the Fake Bank is never called twice.

**Poll the resulting status**

```bash
curl http://localhost:8000/payments/1
```

```json
{
  "id": 1,
  "payment_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "amount": 250.00,
  "currency": "USD",
  "status": "SUCCESS",
  "merchant_reference": "ORDER-1042",
  "description": "Subscription renewal",
  "created_at": "2026-07-16T10:15:00.123Z",
  "updated_at": "2026-07-16T10:15:03.981Z"
}
```

---

## 🖼 Screenshots

> Add screenshots to `docs/images/` using the filenames below.

| | |
|---|---|
| ![Dashboard Overview](docs/images/dashboard-overview.png) | ![Payment Timeline](docs/images/payment-timeline.png) |
| **Dashboard overview** — live stats & infra health | **Payment timeline** — real-time payment feed |
| ![Faults & Retries](docs/images/faults-and-retries.png) | ![Swagger Docs](docs/images/swagger-docs.png) |
| **Faults & Retries panel** — retry attempts and terminal failures | **Swagger / OpenAPI docs** |

---

## 🔮 Future Improvements

- [ ] Enforce JWT auth on `/payments` and `/dashboard/*` (the auth module exists but isn't yet applied as a dependency on those routers)
- [ ] Automated `pytest` suite — currently limited to the manual scripts `test_fake_bank.py` and `test_logging.py`
- [ ] Wire the existing `CircuitBreaker` schema into a real circuit breaker around the Fake Bank client
- [ ] Scheduled health-check poller writing into the existing `HealthSnapshot` table
- [ ] DLQ replay tooling (currently manual, via the RabbitMQ Management UI)
- [ ] Extend `docker-compose.yml` to containerize the API, worker, dashboard, PostgreSQL, and Redis alongside RabbitMQ
- [ ] Outbound webhook/callback notifications on terminal payment state
- [ ] Rate limiting on public endpoints
- [ ] Cursor-based pagination for dashboard log/retry feeds (currently `limit`-only)
- [ ] Prometheus/Grafana metrics exporter alongside the structured logs

---

## 🏆 Resume Highlights

- Designed and built an **event-driven payment processing pipeline** with FastAPI + RabbitMQ, decoupling API response latency from downstream bank-processing time
- Implemented a **self-healing retry engine** with exponential backoff + jitter on a dedicated queue/channel, isolated from the main dispatch path via `prefetch_count` tuning
- Built **production-style idempotency** using Redis distributed locks, preventing duplicate charges under concurrent identical requests
- Engineered **poison-pill protection**: malformed or irrecoverable messages are rejected without requeue and routed to a Dead Letter Queue, guaranteeing the worker process can never crash or infinite-loop
- Implemented **end-to-end distributed tracing** with `structlog` + Python `contextvars`, propagating correlation IDs across an HTTP request and an asynchronous RabbitMQ worker boundary
- Designed a normalized relational schema — `Payment`, `Service`, `RequestLog`, `RetryAttempt`, `CircuitBreaker`, `HealthSnapshot` — with Alembic-managed migrations
- Built a **real-time Next.js/TypeScript observability dashboard** consuming custom FastAPI monitoring endpoints
- Implemented **JWT authentication** with bcrypt password hashing and OAuth2 password-flow login

---

## 🧠 Lessons Learned

- **Idempotency is harder than "add a unique key."** Concurrent identical requests need a distributed lock, not just a cache lookup — otherwise two requests can both miss the cache and both create a payment.
- **Retry state belongs in the message, not in memory.** Encoding `retry_count` and `retry_delay` directly in the RabbitMQ payload made the retry consumer completely stateless and safe to crash and restart.
- **A single queue with one consumer isn't enough once retries exist.** Putting the retry queue on its own channel with a much higher `prefetch_count` was necessary — otherwise a handful of messages sleeping through backoff would starve the main payment queue.
- **"Never crash the worker" has to be a design principle, not an afterthought.** Nested `try/except` at every layer — message parsing, DB transition, bank call, DLQ publish — was needed to guarantee forward progress on every single message.
- **Structured logging context pays for itself immediately** once you need to trace one payment across an HTTP request *and* a fully asynchronous worker process running in a different Python process entirely.
- **A tunable failure simulator is worth building.** Making the Fake Bank's timeout/500/duplicate probabilities configurable made it possible to deterministically exercise retry and DLQ code paths that would otherwise be rare and painful to reproduce on demand.

---

## 📄 License

This repository does not currently include a `LICENSE` file. If you intend to share or reuse this project, adding a permissive license such as **MIT** is recommended — for example:

```
MIT License

Copyright (c) 2026 Shrajal

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```