"""Top-level dashboard entrypoint."""

from dc_mar_sdk.dashboard.app import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("dc_mar_sdk.dashboard.app:app", host="0.0.0.0", port=8000, reload=True)
