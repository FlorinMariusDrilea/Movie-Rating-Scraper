# Official Playwright image: Chromium + all system deps preinstalled.
# The tag version MUST match the playwright version in requirements.txt,
# otherwise the pip package won't find the browsers baked into the image.
# (python:3.11-slim + `playwright install --with-deps` breaks on newer Debian
# releases — e.g. ttf-ubuntu-font-family has no installation candidate.)
FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Drop root: the base image ships a non-privileged 'pwuser'. Own the app dir so
# the dataset cache (backend/data) is writable at runtime.
RUN chown -R pwuser:pwuser /app
USER pwuser

EXPOSE 8000

# Apply migrations, then serve. The database must be reachable at startup
# (compose handles this with a healthcheck-gated depends_on).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
