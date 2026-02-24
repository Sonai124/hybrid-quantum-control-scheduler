FROM python:3.11-slim

WORKDIR /app

RUN python -m pip install --no-cache-dir -U pip

COPY . /app
RUN pip install --no-cache-dir -e ".[dev]"

CMD ["hqcsim", "run", "--policy", "credit", "--t-end", "5"]
