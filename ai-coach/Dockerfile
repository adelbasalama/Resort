FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY templates ./templates
COPY static ./static
COPY seeds ./seeds
CMD ["python", "-m", "app.main"]
