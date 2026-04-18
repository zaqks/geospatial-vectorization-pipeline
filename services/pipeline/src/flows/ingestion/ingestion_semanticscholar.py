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
    base_url: str = Field("https://api.semanticscholar.org/graph/v1/paper/search", alias="BASE_URL")
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
    max_results: int = Field(200, alias="MAX_RESULTS")
    limit_per_query: int = Field(100, alias="LIMIT_PER_QUERY")
    min_citation_count: int = Field(0, alias="MIN_CITATION_COUNT")

    @validator("keywords", pre=True)
    def parse_keywords(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v

    class Config:
        allow_population_by_field_name = True


@task
async def main(params: InputParams | None = None):
    import asyncio

    if params is None:
        params = InputParams()

    logger = get_logger()
    since = datetime.utcnow() - timedelta(days=params.n_days)
    since_timestamp = int(since.timestamp())

    extracted = 0
    data_list = []
    seen_ids = set()

    # Fields to retrieve from Semantic Scholar API
    fields = "paperId,title,abstract,authors,publicationDate,url,citationCount,influentialCitationCount,fieldsOfStudy"

    async with httpx.AsyncClient(timeout=30.0) as client:
        for keyword in params.keywords:
            try:
                # Build query with keyword and fields of study
                query = keyword
                
                # Search papers
                offset = 0
                while offset < params.max_results:
                    try:
                        response = await client.get(
                            params.base_url,
                            params={
                                "query": query,
                                "fields": fields,
                                "limit": min(params.limit_per_query, params.max_results - offset),
                                "offset": offset,
                                "publicationDateOrYear": f"{since.year}-",
                                "minCitationCount": params.min_citation_count,
                            },
                        )
                        response.raise_for_status()
                        result = response.json()

                        papers = result.get("data", [])
                        if not papers:
                            break

                        for paper in papers:
                            try:
                                # Get paper ID
                                paper_id = paper.get("paperId")
                                if not paper_id or paper_id in seen_ids:
                                    continue
                                seen_ids.add(paper_id)

                                # Parse publication date
                                pub_date_str = paper.get("publicationDate")
                                if not pub_date_str:
                                    continue

                                try:
                                    pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
                                except ValueError:
                                    # Try with year only
                                    try:
                                        pub_date = datetime.strptime(pub_date_str, "%Y")
                                    except ValueError:
                                        logger.warning(f"Could not parse date: {pub_date_str}")
                                        continue

                                if pub_date < since:
                                    continue

                                # Get title and abstract
                                title = paper.get("title", "")
                                abstract = paper.get("abstract", "")
                                
                                if not title:
                                    continue

                                # Get authors
                                authors_list = paper.get("authors", [])
                                authors = "; ".join(
                                    a.get("name", "unknown") for a in authors_list
                                ) if authors_list else "unknown"

                                # Get URL
                                paper_url = paper.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"

                                # Get fields of study as tags
                                fields_of_study = paper.get("fieldsOfStudy", [])
                                tags = "; ".join(fields_of_study) if fields_of_study else "untagged"

                                # Add citation metrics to tags
                                citation_count = paper.get("citationCount", 0)
                                influential_citations = paper.get("influentialCitationCount", 0)
                                if citation_count:
                                    tags += f"; citations:{citation_count}"
                                if influential_citations:
                                    tags += f"; influential:{influential_citations}"

                                data = {
                                    "source": "semanticscholar",
                                    "id": paper_id,
                                    "title": title.replace("\n", " "),
                                    "abstract_or_summary": (abstract.replace("\n", " ")[:1000] if abstract else "No abstract"),
                                    "authors": authors,
                                    "date": pub_date.date().isoformat(),
                                    "url": paper_url,
                                    "tags": tags,
                                }
                                data_list.append(data)
                                extracted += 1

                            except (ValueError, KeyError, AttributeError) as e:
                                logger.warning(f"Error parsing paper {paper.get('paperId', 'unknown')}: {e}")
                                continue

                        # Check if there are more results
                        total = result.get("total", 0)
                        offset += len(papers)
                        
                        if offset >= total or offset >= params.max_results:
                            break

                        # Small delay to respect rate limits
                        await asyncio.sleep(0.3)

                    except httpx.HTTPError as e:
                        logger.error(f"HTTP error for keyword '{keyword}' at offset {offset}: {e}")
                        break

            except Exception as e:
                logger.error(f"Unexpected error for keyword '{keyword}': {e}")
                continue

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

    logger.info("Extracted %s rows from Semantic Scholar", extracted)
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
    id="semanticscholar_ingestion",
    description="Ingest recent Semantic Scholar papers matching keywords",
    tasks=[main, trigger_llm_analysis],
    triggers=[
        Trigger(
            id="daily",
            name="Daily at 5 AM",
            description="Run the pipeline every day at 5:00 AM",
            schedule=CronTrigger(hour=5),
        ),
    ],
    params=InputParams,
)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())