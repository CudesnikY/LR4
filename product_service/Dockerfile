FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install flask requests pika google-generativeai flask-cors "python-jose[cryptography]"
CMD ["python", "app.py"]
