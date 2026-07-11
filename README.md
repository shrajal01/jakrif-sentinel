# JakRif Sentinel

A Fault-Tolerant Payment Reliability Platform

## Folder Structure

```
JakRif-Sentinel/
├── app/
│   ├── api/
│   ├── core/
│   ├── database/
│   ├── models/
│   ├── repositories/
│   ├── schemas/
│   ├── services/
│   ├── utils/
│   └── __init__.py
├── worker/
├── fake_bank/
├── dashboard/
├── tests/
├── docker/
├── docs/
├── alembic/
├── .gitignore
├── .env.example
└── README.md
```

## Tech Stack

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker
- RabbitMQ
- Redis

## Setup

### Starting RabbitMQ

Run the provided script to start RabbitMQ locally using Docker:

```bash
start_rabbitmq.bat
```
This will start RabbitMQ and expose the Management UI at `http://localhost:15672`.

### Running Worker

To start the worker process that consumes from RabbitMQ, use the provided script:

```bash
start_worker.bat
```

### Queue Flow

1. The user makes a POST request to `/payments`.
2. The `PaymentService` creates the payment record in PostgreSQL with status `CREATED`.
3. After successful database commit, an event is published to the `payments_exchange` in RabbitMQ.
4. The message is routed to `payments_queue`.
5. The Worker consumes the message from the queue, deserializes the JSON payload, and logs it. (Processing logic to be implemented).
## Architecture

## Features

## API Documentation
