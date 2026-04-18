import os
import gc
import feedparser
from datetime import datetime, timedelta
from urllib.parse import urlencode
from ...utils._tools import bulk_insert_datasources
from typing import List
from pydantic import BaseModel, Field

from apscheduler.triggers.cron import CronTrigger
from plombery import task, get_logger, Trigger, register_pipeline
from pydantic import BaseModel, Field, validator


class InputParams(BaseModel):
    n_days: int = Field(7, alias="N_DAYS")
    base_url: str = Field("http://export.arxiv.org/api/query?", alias="BASE_URL")
    keywords: List[str] = Field(
        [
            "data pipeline",
            "ETL",
            "data lake",
            "warehouse",
            "LLM",
            "agent",
            "retrieval",
            "RAG",
        ],
        alias="KEYWORDS",
    )
    categories: List[str] = Field(
        ["cs.AI", "cs.LG", "cs.DB", "stat.ML"], alias="CATEGORIES"
    )
    max_results: int = Field(200, alias="MAX_RESULTS")

    @validator("keywords", pre=True)
    def parse_keywords(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v

    @validator("categories", pre=True)
    def parse_categories(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v

    class Config:
        allow_population_by_field_name = True


def _build_query(keywords: list[str], categories: list[str]) -> str:
    kw = " OR ".join(f'all:"{k}"' for k in keywords)
    cat = " OR ".join(f"cat:{c}" for c in categories)
    return f"({kw}) AND ({cat})"


@task
async def main(params: InputParams | None = None):
    import asyncio

    if params is None:
        params = InputParams()

    logger = get_logger()
    since = datetime.utcnow() - timedelta(days=params.n_days)

    query = {
        "search_query": _build_query(params.keywords, params.categories),
        "start": 0,
        "max_results": params.max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    # Run feedparser.parse in a thread to avoid blocking event loop
    feed = await asyncio.to_thread(feedparser.parse, params.base_url + urlencode(query))

    extracted = 0
    data_list = []
    
    for e in feed.entries:
        published = datetime.strptime(e.published, "%Y-%m-%dT%H:%M:%SZ")
        if published < since:
            continue

        data = {
            "source": "arxiv",
            "id": e.id.split("/")[-1],
            "title": e.title.replace("\n", " "),
            "abstract_or_summary": e.summary.replace("\n", " "),
            "authors": "; ".join(a.name for a in e.authors),
            "date": published.date().isoformat(),
            "url": e.link,
            "tags": "; ".join(t.term for t in e.tags),
        }
        data_list.append(data)
        extracted += 1

    # Free feed memory immediately after extraction
    del feed
    gc.collect()

    added = 0
    if data_list:
        try:
            # Run bulk_insert_datasources in a thread
            added = await asyncio.to_thread(bulk_insert_datasources, data_list)
        except Exception as e:
            logger.error(f"Error in bulk insert: {e}")
        finally:
            del data_list
            gc.collect()

    logger.info("Extracted %s rows from arXiv", extracted)
    logger.info("Inserted %s new rows into DB", added)
    
    return {"extracted": extracted, "inserted": added}


import httpx


@task
async def trigger_llm_analysis():
    # Trigger LLM analysis after ingestion
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
    id="arxiv_ingestion",
    description="Ingest recent arXiv papers matching keywords",
    tasks=[main, trigger_llm_analysis],
    triggers=[
        Trigger(
            id="daily",
            name="Daily at midnight",
            description="Run the pipeline every day at 12:00 AM",
            schedule=CronTrigger(hour=0),
        ),
    ],
    params=InputParams,
)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
