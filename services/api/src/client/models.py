import uuid

from sqlalchemy import Column, Float, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import relationship

from ..utils._db import Base

class Input(Base):
	__tablename__ = "inputs"

	uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
	image = Column(LargeBinary, nullable=False)
	lat1 = Column(Float, nullable=False)
	lat2 = Column(Float, nullable=False)
	lng1 = Column(Float, nullable=False)
	lng2 = Column(Float, nullable=False)
	percent_progress = Column(Integer, nullable=False, default=0)

	output = relationship(
		"Output",
		back_populates="input",
		uselist=False,
		cascade="all, delete-orphan",
	)


class Output(Base):
	__tablename__ = "outputs"

	uuid = Column(String(36), ForeignKey("inputs.uuid"), primary_key=True)
	image = Column(LargeBinary, nullable=False)

	input = relationship("Input", back_populates="output")
	output_files = relationship(
		"OutputFile",
		back_populates="output",
		cascade="all, delete-orphan",
	)


class OutputFile(Base):
	__tablename__ = "output_files"

	id = Column(Integer, primary_key=True, index=True)
	output_uuid = Column(String(36), ForeignKey("outputs.uuid"), nullable=False)
	name = Column(String, nullable=False)
	file = Column(LargeBinary, nullable=False)

	output = relationship("Output", back_populates="output_files")
