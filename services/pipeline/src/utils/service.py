import uuid
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from src.utils.models import Input, Output, OutputFile

PROGRESS_STEP = 20
MOCK_FILE_NAMES = [
    "giphy.gif",
    "output_1.tif",
    "output_2.tif",
    "output_3.tif",
    "output_4.tif",
]


@lru_cache(maxsize=1)
def _load_mock_media_bytes() -> bytes:
    giphy_path = Path(__file__).resolve().parents[2] / "static" / "giphy.gif"
    return giphy_path.read_bytes()


def save_mock_input(
    db: Session,
    image_bytes: bytes,
    lat1: float,
    lat2: float,
    lng1: float,
    lng2: float,
) -> str:
    upload_uuid = str(uuid.uuid4())

    db_input = Input(
        uuid=upload_uuid,
        image=image_bytes,
        lat1=lat1,
        lat2=lat2,
        lng1=lng1,
        lng2=lng2,
        percent_progress=0,
    )
    db.add(db_input)
    db.commit()

    return upload_uuid


def get_mock_result(db: Session, upload_uuid: str) -> tuple[Input | None, Output | None]:
    db_input = db.get(Input, upload_uuid)
    if not db_input:
        return None, None

    current_progress = int(getattr(db_input, "percent_progress", 0))
    if current_progress < 100:
        next_progress = min(100, current_progress + PROGRESS_STEP)
        setattr(db_input, "percent_progress", next_progress)
        db.commit()
        db.refresh(db_input)
        current_progress = next_progress

    if current_progress < 100:
        return db_input, None

    db_output = db.get(Output, upload_uuid)
    if not db_output:
        try:
            media_bytes = _load_mock_media_bytes()
        except OSError:
            media_bytes = db_input.image

        db_output = Output(uuid=upload_uuid, image=media_bytes)
        db.add(db_output)
        db.flush()

        for file_name in MOCK_FILE_NAMES:
            db.add(OutputFile(output_uuid=upload_uuid, name=file_name, file=media_bytes))
        db.commit()
        db.refresh(db_output)

    return db_input, db_output
