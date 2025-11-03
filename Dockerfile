FROM python:3.12-slim
 

RUN mkdir /app
 

WORKDIR /app
 

ENV PYTHONDONTWRITEBYTECODE=1

ENV PYTHONUNBUFFERED=1 
 

RUN pip install --upgrade pip 
 

COPY requirements.txt  /app/


RUN pip install --no-cache-dir -r requirements.txt
 

COPY . /app/
 

EXPOSE 8000
 
# Run Django’s development server
CMD ["uvicorn", "chatbot.asgi:application", "--host", "0.0.0.0", "--port", "8000", "--reload"]
