# Local/staging CPU runtime. Public release needs a trusted HTTPS reverse proxy,
# authenticated identities, access limits and verified image publication rights.
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-api.txt requirements-ml.txt ./
RUN python -m pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
      'torch==2.10.0+cpu' 'torchvision==0.25.0+cpu' \
    && python -m pip install --no-cache-dir -r requirements-ml.txt
COPY backend ./backend
COPY src ./src
COPY live.html live.js live.css styles.css index.html app.js ./
RUN useradd -u 10001 -m -s /usr/sbin/nologin tdm
USER tdm
EXPOSE 8000
CMD ["uvicorn", "backend.service:get_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
