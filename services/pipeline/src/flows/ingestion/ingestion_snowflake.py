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
    rss_url: str = Field("https://www.snowflake.com/en/blog/feed/", alias="RSS_URL")
    keywords: List[str] = Field(
        [
            "AutoML",
            "data quality",
            "data pipeline",
            "ETL",
            "data warehouse",
            "data lake",
            "Snowpark",
            "data sharing",
            "data governance",
            "SQL",
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

    if params is None:
        params = InputParams()

    logger = get_logger()
    since = datetime.utcnow() - timedelta(days=params.n_days)

    # Run feedparser.parse in a thread to avoid blocking event loop
    try:
        feed = await asyncio.to_thread(feedparser.parse, params.rss_url)
    except Exception as e:
        logger.error(f"Error parsing RSS feed: {e}")
        return {"extracted": 0, "inserted": 0}

    extracted = 0
    data_list = []

    for e in feed.entries[:params.max_results]:
        try:
            # Parse published date
            published = None
            if hasattr(e, 'published_parsed') and e.published_parsed:
                published = datetime(*e.published_parsed[:6])
            elif hasattr(e, 'published'):
                try:
                    published = datetime.strptime(e.published, "%a, %d %b %Y %H:%M:%S %Z")
                except ValueError:
                    try:
                        published = datetime.strptime(e.published, "%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        logger.warning(f"Could not parse date: {e.published}")
                        continue

            if not published or published < since:
                continue

            # Get title and summary
            title = e.get('title', '').replace("\n", " ")
            summary = e.get('summary', e.get('description', '')).replace("\n", " ")

            # Check if matches keywords
            combined_text = f"{title} {summary}"
            if not _match_keywords(combined_text, params.keywords):
                continue

            # Get author
            author = "Snowflake"
            if hasattr(e, 'author'):
                author = e.author
            elif hasattr(e, 'authors') and e.authors:
                author = "; ".join(a.get('name', 'unknown') for a in e.authors)

            # Get tags
            tags = "snowflake; data warehouse"
            if hasattr(e, 'tags') and e.tags:
                tags = "; ".join(t.get('term', '') for t in e.tags)

            data = {
                "source": "snowflake",
                "id": e.get('id', e.get('link', '')).split('/')[-1],
                "title": title,
                "abstract_or_summary": summary[:1000] if summary else "No description",
                "authors": author,
                "date": published.date().isoformat(),
                "url": e.get('link', ''),
                "tags": tags,
            }
            data_list.append(data)
            extracted += 1

        except Exception as e:
            logger.warning(f"Error parsing entry: {e}")
            continue

    # Free feed memory immediately after extraction
    del feed
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

    logger.info("Extracted %s rows from Snowflake blog", extracted)
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
    id="snowflake_ingestion",
    description="Ingest recent Snowflake blog posts matching keywords",
    tasks=[main, trigger_llm_analysis],
    triggers=[
        Trigger(
            id="daily",
            name="Daily at 6 AM",
            description="Run the pipeline every day at 6:00 AM",
            schedule=CronTrigger(hour=6),
        ),
    ],
    params=InputParams,
)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())