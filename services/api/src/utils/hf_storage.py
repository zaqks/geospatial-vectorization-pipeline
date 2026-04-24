import os
from functools import lru_cache
from tempfile import TemporaryDirectory

from huggingface_hub import batch_bucket_files, download_bucket_files, login


def _get_hf_token() -> str:
    token = os.getenv("HF_TOKEN", "").strip()
    if not token:
        raise ValueError("HF_TOKEN is required for Hugging Face storage")
    return token


def _get_hf_repo_id() -> str:
    return os.getenv("HF_BUCKET_REPO_ID", "zaqks/sig-bucket").strip()


@lru_cache(maxsize=1)
def _login_hf() -> str:
    token = _get_hf_token()
    login(token=token, add_to_git_credential=False)
    return token


def upload_to_hf(content: bytes, path_in_repo: str) -> str:
    _login_hf()
    repo_id = _get_hf_repo_id()

    batch_bucket_files(repo_id, add=[(content, path_in_repo)])
    return path_in_repo


def download_from_hf(path_in_repo: str) -> bytes:
    _login_hf()
    repo_id = _get_hf_repo_id()

    with TemporaryDirectory() as temp_dir:
        local_path = os.path.join(temp_dir, "download.bin")
        download_bucket_files(repo_id, files=[(path_in_repo, local_path)])
        with open(local_path, "rb") as handle:
            return handle.read()