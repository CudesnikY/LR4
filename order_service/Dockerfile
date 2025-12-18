FROM python:3.10-slim
RUN apt-get update && apt-get install -y sqlite3
WORKDIR /app
COPY . .
RUN pip install flask requests pika openai flask-cors "python-jose[cryptography]"
CMD sh -c "python db.py && python app.py & python outbox_worker.py & python saga_orchestrator.py"