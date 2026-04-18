import os
import gc
from datetime import datetime, timedelta
from typing import List
from pydantic import BaseModel, Field, validator

from apscheduler.triggers.cron import CronTrigger
from plombery import task, get_logger, Trigger, register_pipeline
import httpx


class InputParams(BaseModel):
    n_days: int = Field(7, alias="N_DAYS")
    base_url: str = Field("https://paperswithcode.com/api/v1/papers/", alias="BASE_URL")
    keywords: List[str] = Field(
        [
            "AutoML",
            "retrieval",
            "data lake",
            "data pipeline",
            "ETL",
            "data cleaning",
            "warehouse",
            "RAG",
            "LLM",
            "agent"
        ],
        alias="KEYWORDS",
    )
    areas: List[str] = Field(
        ["machine-learning", "natural-language-processing", "data-mining", "databases", "information-retrieval", "knowledge-graphs"],
        alias="AREAS",
    )
    max_results: int = Field(200, alias="MAX_RESULTS")
    items_per_page: int = Field(50, alias="ITEMS_PER_PAGE")

    @validator("keywords", pre=True)
    def parse_keywords(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v

    @validator("areas", pre=True)
    def parse_areas(cls, v):
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

    extracted = 0
    data_list = []

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch papers page by page
        page = 1
        total_fetched = 0

        while total_fetched < params.max_results:
            try:
                response = await client.get(
                    params.base_url,
                    params={
                        "page": page,
                        "items_per_page": params.items_per_page,
                    },
                )
                response.raise_for_status()
                result = response.json()

                papers = result.get("results", [])
                if not papers:
                    break

                for paper in papers:
                    try:
                        # Parse published date
                        published_str = paper.get("published")
                        if not published_str:
                            continue

                        # Handle different date formats
                        try:
                            if "T" in published_str:
                                # ISO format
                                if published_str.endswith("Z"):
                                    published_str = published_str[:-1]
                                published = datetime.fromisoformat(published_str)
                            else:
                                # Date only format
                                published = datetime.strptime(published_str, "%Y-%m-%d")
                        except ValueError:
                            logger.warning(f"Could not parse date: {published_str}")
                            continue

                        if published < since:
                            continue

                        # Check if paper matches keywords or areas
                        title = paper.get("title", "")
                        abstract = paper.get("abstract", "")
                        combined_text = f"{title} {abstract}"

                        # Check keywords match
                        if not _match_keywords(combined_text, params.keywords):
                            continue

                        # Get paper ID
                        paper_id = paper.get("id", paper.get("paper_url", "").split("/")[-1])

                        # Get authors
                        authors_list = paper.get("authors", [])
                        if isinstance(authors_list, list):
                            authors = "; ".join(authors_list)
                        else:
                            authors = str(authors_list) if authors_list else "unknown"

                        # Get URL
                        paper_url = paper.get("url_pdf") or paper.get("url_abs") or paper.get("paper_url", "")
                        if not paper_url.startswith("http"):
                            paper_url = f"https://paperswithcode.com/paper/{paper_id}"

                        # Get tasks/methods as tags
                        tasks = paper.get("tasks", [])
                        methods = paper.get("methods", [])
                        all_tags = []
                        if isinstance(tasks, list):
                            all_tags.extend(tasks)
                        if isinstance(methods, list):
                            all_tags.extend(methods)

                        data = {
                            "source": "paperswithcode",
                            "id": paper_id,
                            "title": title.replace("\n", " "),
                            "abstract_or_summary": abstract.replace("\n", " ")[:1000] if abstract else "No abstract",
                            "authors": authors,
                            "date": published.date().isoformat(),
                            "url": paper_url,
                            "tags": "; ".join(all_tags) if all_tags else "untagged",
                        }
                        data_list.append(data)
                        extracted += 1

                    except (ValueError, KeyError, AttributeError) as e:
                        logger.warning(f"Error parsing paper {paper.get('id', 'unknown')}: {e}")
                        continue

                total_fetched += len(papers)
                page += 1

                # Check if there are more pages
                if not result.get("next"):
                    break

                # Small delay to be polite to the API
                await asyncio.sleep(0.5)

            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching page {page}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error on page {page}: {e}")
                break

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

    logger.info("Extracted %s rows from Papers with Code", extracted)
    logger.info("Inserted %s new rows into DB", added)

    return {"extracted": extracted, "inserted": added}


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
    id="paperswithcode_ingestion",
    description="Ingest recent Papers with Code matching keywords",
    tasks=[main, trigger_llm_analysis],
    triggers=[
        Trigger(
            id="daily",
            name="Daily at 4 AM",
            description="Run the pipeline every day at 4:00 AM",
            schedule=CronTrigger(hour=4),
        ),
    ],
    params=InputParams,
)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())