FROM python:3.12-slim
RUN pip install --no-cache-dir pymysql clickhouse-connect pymonetdb
COPY harness.py /harness.py
ENTRYPOINT ["python3", "/harness.py"]
