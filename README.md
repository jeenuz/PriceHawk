# PriceHawk — E-commerce Price Intelligence System

Track and predict prices across multiple e-commerce platforms using
web scraping, NLP product matching, and ML forecasting.

## Tech Stack
- **Scraping**: Scrapy, Playwright
- **ML**: Prophet, XGBoost, Sentence-BERT, SHAP
- **API**: FastAPI, WebSockets, JWT auth
- **DB**: PostgreSQL, Redis
- **Infra**: Docker, Airflow, GitHub Actions

## Setup
```bash
git clone https://github.com/jeenuz/pricehawk
cd pricehawk
python -m venv pricehawk
source pricehawk/bin/activate   # Windows: pricehawk\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in your values
```

## Project Structure

| Folder | Purpose |
|--------|---------|
| `scrapers/` | Scrapy spiders + middlewares |
| `models/` | ML training + inference |
| `api/` | FastAPI routes + schemas |
| `db/` | SQLAlchemy models + migrations |
| `tests/` | pytest test suite |

## Phases

| Phase | What gets built |
|-------|----------------|
| 1 | Project setup & folder structure |
| 2 | Scrapy spider — scrape real prices |
| 3 | PostgreSQL database + price history |
| 4 | Product matching across retailers |
| 5 | ML models — forecast & drop prediction |
| 6 | FastAPI backend + alerts |
| 7 | Docker, Airflow, deployment |
```