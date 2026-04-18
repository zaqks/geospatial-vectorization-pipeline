from ._db import SessionLocal, Datasource, DatasourceAnalysis, Reports, Documents
from sqlalchemy.exc import IntegrityError

# --- Utility function to save report and documents ---
def save_report_and_documents(output_dir, session=None):
    """
    Creates a Reports entry with the timestamp from the output_dir name, and saves Documents for all relevant files in the directory.
    Args:
        output_dir (str): Path to the output directory (e.g., /tmp/report_YYYYMMDD_HHMMSS)
        session: Optional SQLAlchemy session. If None, a new session is created and closed inside.
    Returns:
        report_id (int): The ID of the created Reports entry.
    """
    import os
    import gc
    from datetime import datetime

    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True
    try:
        # Extract timestamp from folder name (assumes /tmp/report_YYYYMMDD_HHMMSS)
        folder_name = os.path.basename(output_dir)
        try:
            ts_str = folder_name.split('_', 1)[-1]
            created_at = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
        except Exception:
            created_at = datetime.utcnow()

        # Create Reports entry
        report = Reports(created_at=created_at)
        session.add(report)
        session.flush()  # Get report.id

        # File types to save: .md, .png, .jpg, .jpeg, .svg
        valid_exts = {".md", ".png", ".jpg", ".jpeg", ".svg"}
        for fname in os.listdir(output_dir):
            fpath = os.path.join(output_dir, fname)
            if not os.path.isfile(fpath):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in valid_exts:
                continue
            with open(fpath, "rb") as f:
                file_bytes = f.read()
            doc = Documents(name=fname, file=file_bytes, report_id=report.id)
            session.add(doc)
            del file_bytes
            gc.collect()

        session.commit()
        return report.id
    finally:
        if own_session:
            session.close()
            gc.collect()


def exists_source_by_url(url: str) -> bool:
    """Return True if a datasource with `url` already exists."""
    session = SessionLocal()
    try:
        return session.query(Datasource).filter(Datasource.url == url).first() is not None
    finally:
        session.close()


def insert_datasource(data: dict, session=None) -> bool:
    """Insert a datasource record if the URL is not present.

    `data` should contain keys: source, external_id, title, abstract_or_summary,
    authors, date, url, tags

    Returns True if inserted, False if skipped because of duplicate url.
    Raises on unexpected DB errors.
    """
    url = data.get("url")
    if not url:
        raise ValueError("`url` is required to insert a datasource")

    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True

    try:
        # quick duplicate check
        if session.query(Datasource).filter(Datasource.url == url).first():
            return False

        ds = Datasource(
            source=data.get("source"),
            external_id=data.get("id") or data.get("external_id"),
            title=data.get("title"),
            abstract_or_summary=data.get("abstract_or_summary"),
            authors=data.get("authors"),
            date=data.get("date"),
            url=url,
            tags=data.get("tags"),
        )
        session.add(ds)
        if own_session:
            session.commit()
        else:
            session.flush()
        return True
    except IntegrityError:
        if own_session:
            session.rollback()
        return False
    finally:
        if own_session:
            session.close()


def bulk_insert_datasources(datasources: list[dict]) -> int:
    """Bulk insert datasources, skipping duplicates."""
    import gc
    
    if not datasources:
        return 0
    
    session = SessionLocal()
    added = 0
    try:
        urls = [d['url'] for d in datasources if d.get('url')]
        if not urls:
            return 0
            
        # Check existing in chunks to avoid too large query
        existing_urls = set()
        chunk_size = 500
        for i in range(0, len(urls), chunk_size):
            chunk = urls[i:i+chunk_size]
            res = session.query(Datasource.url).filter(Datasource.url.in_(chunk)).all()
            existing_urls.update(r[0] for r in res)
            del res, chunk
            gc.collect()
            
        to_insert = []
        seen_in_batch = set()
        
        for d in datasources:
            url = d.get('url')
            if url and url not in existing_urls and url not in seen_in_batch:
                ds = Datasource(
                    source=d.get("source"),
                    external_id=d.get("id") or d.get("external_id"),
                    title=d.get("title"),
                    abstract_or_summary=d.get("abstract_or_summary"),
                    authors=d.get("authors"),
                    date=d.get("date"),
                    url=url,
                    tags=d.get("tags"),
                )
                to_insert.append(ds)
                seen_in_batch.add(url)
        
        del existing_urls, seen_in_batch, urls
        gc.collect()
        
        if to_insert:
            session.bulk_save_objects(to_insert)
            session.commit()
            added = len(to_insert)
            del to_insert
            gc.collect()
            
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        gc.collect()
    return added


# --- Functions for DatasourceAnalysis ---
def exists_analysis_by_datasource_id(datasource_id: int, session=None) -> bool:
    """Return True if a DatasourceAnalysis with the given datasource_id exists."""
    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True
    try:
        return session.query(DatasourceAnalysis).filter(DatasourceAnalysis.datasource_id == datasource_id).first() is not None
    finally:
        if own_session:
            session.close()


def insert_datasource_analysis(data: dict, session=None) -> bool:
    """Insert a DatasourceAnalysis record if the datasource_id is not present.

    `data` should contain at least: datasource_id. Other fields are optional.
    Returns True if inserted, False if skipped because of duplicate datasource_id.
    Raises on unexpected DB errors.
    """
    datasource_id = data.get("datasource_id")
    if datasource_id is None:
        raise ValueError("`datasource_id` is required to insert a DatasourceAnalysis")

    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True

    try:
        # quick duplicate check
        if session.query(DatasourceAnalysis).filter(DatasourceAnalysis.datasource_id == datasource_id).first():
            return False

        analysis = DatasourceAnalysis(
            datasource_id=datasource_id,
            topics=data.get("topics"),
            keywords=data.get("keywords"),
            emerging_algorithms=data.get("emerging_algorithms"),
            summary=data.get("summary"),
            impact=data.get("impact"),
            exported=data.get("exported", False),
        )
        session.add(analysis)
        if own_session:
            session.commit()
        else:
            session.flush()
        return True
    except IntegrityError:
        if own_session:
            session.rollback()
        return False
    finally:
        if own_session:
            session.close()

# non exported stuff
def fetch_analysis_rows(session, num_rows):
    return session.query(DatasourceAnalysis).filter(DatasourceAnalysis.exported == False).order_by(DatasourceAnalysis.id).limit(num_rows).all()
    # return session.query(DatasourceAnalysis).order_by(DatasourceAnalysis.id).limit(num_rows).all()
