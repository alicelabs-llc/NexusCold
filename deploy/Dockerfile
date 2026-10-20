FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir 'aiohttp>=3.12,<4'
COPY german_gateway.py german_agent.py data_quality.py network_safety.py ./
RUN useradd --uid 10001 --create-home german
USER german
ENV GERMAN_BIND=0.0.0.0
EXPOSE 8080
CMD ["python", "german_gateway.py"]
