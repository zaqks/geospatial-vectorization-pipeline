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
    base_url: str = Field("https://huggingface.co/api/models", alias="BASE_URL")
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
    tasks: List[str] = Field(
        ["time-series-forecasting", "table-question-answering", "tabular-regression", "feature-extraction", "zero-shot-classification", "tabular-classification"],
        alias="TASKS",
    )
    max_results: int = Field(200, alias="MAX_RESULTS")
    sort: str = Field("lastModified", alias="SORT")
    direction: int = Field(-1, alias="DIRECTION")

    @validator("keywords", pre=True)
    def parse_keywords(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v

    @validator("tasks", pre=True)
    def parse_tags(cls, v):
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
        for task in params.tasks:
            try:
                # Query Hugging Face API with task filter
                response = await client.get(
                    params.base_url,
                    params={
                        "filter": task,
                        "sort": params.sort,
                        "direction": params.direction,
                        "limit": params.max_results,
                    },
                )
                response.raise_for_status()
                models = response.json()

                for model in models:
                    try:
                        # Parse lastModified date
                        last_modified_str = model.get("lastModified")
                        if not last_modified_str:
                            continue

                        # Handle ISO format with timezone
                        if last_modified_str.endswith("Z"):
                            last_modified_str = last_modified_str[:-1]
                        elif "+" in last_modified_str:
                            last_modified_str = last_modified_str.split("+")[0]

                        last_modified = datetime.fromisoformat(last_modified_str)

                        if last_modified < since:
                            continue

                        # Check if model matches keywords
                        model_id = model.get("modelId", model.get("id", ""))
                        description = model.get("description", "")
                        combined_text = f"{model_id} {description}"

                        if not _match_keywords(combined_text, params.keywords):
                            continue

                        data = {
                            "source": "huggingface",
                            "id": model_id,
                            "title": model_id.split("/")[-1] if "/" in model_id else model_id,
                            "abstract_or_summary": description[:500] if description else "No description",
                            "authors": model_id.split("/")[0] if "/" in model_id else "unknown",
                            "date": last_modified.date().isoformat(),
                            "url": f"https://huggingface.co/{model_id}",
                            "tags": "; ".join(model.get("tags", [])),
                        }
                        data_list.append(data)
                        extracted += 1

                    except (ValueError, KeyError, AttributeError) as e:
                        logger.warning(f"Error parsing model {model.get('id', 'unknown')}: {e}")
                        continue

            except httpx.HTTPError as e:
                logger.error(f"HTTP error fetching task {task}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error for task {task}: {e}")
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

    logger.info("Extracted %s rows from Hugging Face", extracted)
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
    id="huggingface_ingestion",
    description="Ingest recent Hugging Face models matching keywords",
    tasks=[main, trigger_llm_analysis],
    triggers=[
        Trigger(
            id="daily",
            name="Daily at 2 AM",
            description="Run the pipeline every day at 2:00 AM",
            schedule=CronTrigger(hour=2),
        ),
    ],
    params=InputParams,
)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())