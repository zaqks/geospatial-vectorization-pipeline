import os
from functools import lru_cache
from io import BytesIO

from huggingface_hub import HfApi, hf_hub_download, login


def _get_hf_token() -> str:
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        raise ValueError("HF_TOKEN is required for Hugging Face storage")
    return token


def _get_hf_repo_id() -> str:
    return os.getenv("HF_BUCKET_REPO_ID", "zaqks/sig-pipeline").strip()


def _get_hf_repo_type() -> str:
    return os.getenv("HF_BUCKET_REPO_TYPE", "space").strip()


@lru_cache(maxsize=1)
def _login_hf() -> str:
    token = _get_hf_token()
    login(token=token, add_to_git_credential=False)
    return token


def upload_to_hf(content: bytes, path_in_repo: str) -> str:
    token = _login_hf()
    repo_id = _get_hf_repo_id()
    repo_type = _get_hf_repo_type()

    api = HfApi(token=token)
    api.upload_file(
        path_or_fileobj=BytesIO(content),
        path_in_repo=path_in_repo,
        repo_id=repo_id,
        repo_type=repo_type,
        token=token,
    )
    return path_in_repo


def download_from_hf(path_in_repo: str) -> bytes:
    token = _login_hf()
    repo_id = _get_hf_repo_id()
    repo_type = _get_hf_repo_type()

    local_file = hf_hub_download(
        repo_id=repo_id,
        repo_type=repo_type,
        filename=path_in_repo,
        token=token,
    )
    with open(local_file, "rb") as handle:
        return handle.read()