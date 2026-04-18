from sqlalchemy.orm import Session

from .models import Input, Output, OutputFile

HARDCODED_UUID = "550e8400-e29b-41d4-a716-446655440000"
PROGRESS_STEP = 20
MOCK_FILE_NAMES = [
    "output_1.tif",
    "output_2.tif",
    "output_3.tif",
    "output_4.tif",
]


def save_mock_input(
    db: Session,
    image_bytes: bytes,
    lat1: float,
    lat2: float,
    lng1: float,
    lng2: float,
) -> str:
    existing = db.get(Input, HARDCODED_UUID)
    if existing:
        db.query(OutputFile).filter(OutputFile.output_uuid == existing.uuid).delete()
        db.query(Output).filter(Output.uuid == existing.uuid).delete()
        db.delete(existing)
        db.flush()

    db_input = Input(
        uuid=HARDCODED_UUID,
        image=image_bytes,
        lat1=lat1,
        lat2=lat2,
        lng1=lng1,
        lng2=lng2,
        percent_progress=0,
    )
    db.add(db_input)
    db.commit()

    return HARDCODED_UUID


def get_mock_result(db: Session, upload_uuid: str) -> tuple[Input | None, Output | None]:
    # Keep current mock behavior: ignore user-provided UUID and use one fixed UUID.
    upload_uuid = HARDCODED_UUID
    db_input = db.get(Input, upload_uuid)
    if not db_input:
        return None, None

    if db_input.percent_progress < 100:
        db_input.percent_progress = min(100, db_input.percent_progress + PROGRESS_STEP)
        db.commit()
        db.refresh(db_input)

    if db_input.percent_progress < 100:
        return db_input, None

    db_output = db.get(Output, upload_uuid)
    if not db_output:
        db_output = Output(uuid=upload_uuid, image=db_input.image)
        db.add(db_output)
        db.flush()

        for file_name in MOCK_FILE_NAMES:
            db.add(OutputFile(output_uuid=upload_uuid, name=file_name, file=db_input.image))
        db.commit()
        db.refresh(db_output)

    return db_input, db_output