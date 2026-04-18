import os
import gc
import feedparser
from datetime import datetime, timedelta
from typing import List
from pydantic import BaseModel, Field, validator

from apscheduler.triggers.cron import CronTrigger
from plombery import task, get_logger, Trigger, register_pipeline


class InputParams(BaseModel):
    n_days: int = Field(7, alias="N_DAYS")
    base_url: str = Field("https://www.databricks.com/blog", alias="BASE_URL")
    keywords: List[str] = Field(
        [
            "AutoML",
            "data quality",
            "data pipeline",
            "ETL",
            "data lake",
            "lakehouse",
            "Delta Lake",
            "Apache Spark",
            "MLOps",
            "feature store",
        ],
        alias="KEYWORDS",
    )
    max_results: int = Field(100, alias="MAX_RESULTS")

    @validator("keywords", pre=True)
    def parse_keywords(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v

    class Config:
        allow_population_by_field_name = True


def _match_keywords(text: str, keywords: List[str]) -> bool:
    """Check if any keyword appears in the text (case insensitive)"""
    if not text:
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


@task
async def main(params: InputParams | None = None):
    import asyncio
    import httpx
    from bs4 import BeautifulSoup

    if params is None:
        params = InputParams()

    logger = get_logger()
    since = datetime.utcnow() - timedelta(days=params.n_days)

    extracted = 0
    data_list = []

    try:
        # Scrape Databricks blog page
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(params.base_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find all blog post cards (adapt selector based on actual HTML structure)
            articles = soup.find_all('article', limit=params.max_results)
            
            if not articles:
                # Try alternative selectors
                articles = soup.find_all(['div', 'section'], class_=['post', 'blog-post', 'card'], limit=params.max_results)
            
            for article in articles:
                try:
                    # Extract title
                    title_elem = article.find(['h2', 'h3', 'h4', 'a'])
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    
                    # Extract URL
                    link_elem = article.find('a', href=True)
                    if not link_elem:
                        continue
                    url = link_elem['href']
                    if not url.startswith('http'):
                        url = f"https://www.databricks.com{url}"
                    
                    # Extract date (try multiple formats)
                    date_elem = article.find(['time', 'span'], class_=['date', 'published', 'post-date'])
                    pub_date = None
                    if date_elem:
                        date_str = date_elem.get('datetime', date_elem.get_text(strip=True))
                        try:
                            # Try ISO format
                            if 'T' in date_str:
                                pub_date = datetime.fromisoformat(date_str.replace('Z', ''))
                            else:
                                # Try common formats
                                for fmt in ['%B %d, %Y', '%Y-%m-%d', '%d %B %Y']:
                                    try:
                                        pub_date = datetime.strptime(date_str, fmt)
                                        break
                                    except ValueError:
                                        continue
                        except (ValueError, AttributeError):
                            pass
                    
                    # If no date found or too old, skip
                    if not pub_date or pub_date < since:
                        continue
                    
                    # Extract description/summary
                    desc_elem = article.find(['p', 'div'], class_=['excerpt', 'summary', 'description'])
                    description = desc_elem.get_text(strip=True) if desc_elem else ""
                    
                    # Check if matches keywords
                    combined_text = f"{title} {description}"
                    if not _match_keywords(combined_text, params.keywords):
                        continue
                    
                    # Extract author (if available)
                    author_elem = article.find(['span', 'div', 'a'], class_=['author', 'by'])
                    author = author_elem.get_text(strip=True) if author_elem else "Databricks"
                    
                    data = {
                        "source": "databricks",
                        "id": url.split('/')[-1] or f"databricks_{extracted}",
                        "title": title.replace("\n", " "),
                        "abstract_or_summary": description[:500] if description else "No description",
                        "authors": author,
                        "date": pub_date.date().isoformat(),
                        "url": url,
                        "tags": "databricks; data engineering; lakehouse",
                    }
                    data_list.append(data)
                    extracted += 1

                except Exception as e:
                    logger.warning(f"Error parsing article: {e}")
                    continue

    except httpx.HTTPError as e:
        logger.error(f"HTTP error fetching Databricks blog: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

    # Free memory
    gc.collect()

    added = 0
    if data_list:
        try:
            from ...utils._tools import bulk_insert_datasources
            # Run bulk_insert_datasources in a thread
            added = await asyncio.to_thread(bulk_insert_datasources, data_list)
        except Exception as e:
            logger.error(f"Error in bulk insert: {e}")
        finally:
            del data_list
            gc.collect()

    logger.info("Extracted %s rows from Databricks blog", extracted)
    logger.info("Inserted %s new rows into DB", added)

    return {"extracted": extracted, "inserted": added}


@task
async def trigger_llm_analysis():
    # Trigger LLM analysis after ingestion
    import httpx
    import asyncio
    logger = get_logger()
    
    max_retries = 3
    retry_delay = 60  # seconds
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f'{os.getenv("HOST2")}/api/pipelines/datasource_analysis_llm/run',
                    json={"params": {}},
                )
                response.raise_for_status()

            logger.info(f"LLM analysis triggered: {response.status_code}")
            try:
                return response.json()
            except Exception:
                logger.warning(f"Non-JSON response: {response.text}")
                return {"status_code": response.status_code, "text": response.text}
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Trigger LLM analysis attempt {attempt + 1} failed: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to trigger LLM analysis after {max_retries} attempts: {e}")
                return {"error": str(e)}


register_pipeline(
    id="databricks_ingestion",
    description="Ingest recent Databricks blog posts matching keywords",
    tasks=[main, trigger_llm_analysis],
    triggers=[
        Trigger(
            id="daily",
            name="Daily at 1 AM",
            description="Run the pipeline every day at 1:00 AM",
            schedule=CronTrigger(hour=1),
        ),
    ],
    params=InputParams,
)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())