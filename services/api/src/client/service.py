import uuid

from sqlalchemy.orm import Session

from .models import Input, Output

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
        return db_input, None

    db_output = db.get(Output, upload_uuid)
    return db_input, db_output