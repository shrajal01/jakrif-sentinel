@echo off
echo Starting RabbitMQ using Docker...
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
echo RabbitMQ started. Management UI available at http://localhost:15672
