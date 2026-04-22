# from src.example import *
# from src.ingestion_vldb_sigmod import *

# from src.flows.ingestion.ingestion_arxiv import *
# from src.flows.ingestion.ingestion_huggingface import *
# from src.flows.ingestion.ingestion_nvidia import *

# from src.flows.ingestion.ingestion_databricks import *

# # from src.flows.ingestion.ingestion_paperswithcode import *
# # from src.flows.ingestion.ingestion_semanticscholar import *
# from src.flows.ingestion.ingestion_snowflake import *  # empty data

# from src.flows.analysis.analysis_llm import *
# from src.flows.gen.report_generation import *
from src.flows.workspace.setup_workspace import *
from src.flows.georef.flow_1_georef import *
from src.flows.vecto.flow_2_vectorization_line import *
from src.flows.vecto.flow_2_vectorization_dotted import *
from src.flows.vecto.flow_2_vectorization_poly import *
from src.flows.cleaning.flow_3_clean_gapfill import *
from src.flows.cleaning.flow_3_clean_noise_poly import *
from src.flows.viz.flow_4_viz_line import *
from src.flows.viz.flow_4_viz_poly import *
from src.flows.workspace.flow_5_export_output import *
from src.flows.workspace.clean_workspace import *

import uvicorn
import os

if __name__ == "__main__":

    uvicorn.run(
        "plombery:get_app",
        reload=os.getenv("RELOAD") != "false",
        factory=True,
        port=8080,
        host="0.0.0.0",
        # workers=4,
    )
