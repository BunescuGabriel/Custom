import json
import time
from threading import Event

import pytest

from src.db.models import GenerationJob
from src.db.repositories import create_job, get_record
from src.services import job_service
from src.services.job_service import cancel_job, recover_interrupted_jobs, submit_job


def test_job_survives_page_and_can_be_cancelled(isolated_store, audio_parameters, monkeypatch):
    started = Event()

    def generate(**kwargs):
        started.set()
        while True:
            kwargs["control"].check()
            time.sleep(0.01)

    monkeypatch.setattr(job_service, "generate_audio_record", generate)
    parameters = {"audio": audio_parameters, "output_format": "MP3"}
    original = json.dumps(parameters)
    job_id = submit_job(parameters)
    assert started.wait(5)
    job = get_record(GenerationJob, job_id)
    assert job.status == "running"
    assert json.loads(job.parameters) == parameters
    with pytest.raises(ValueError, match="altă generare"):
        submit_job(parameters)
    recover_interrupted_jobs()
    assert get_record(GenerationJob, job_id).status == "running"
    cancel_job(job_id)
    for _ in range(500):
        if get_record(GenerationJob, job_id).status == "cancelled":
            break
        time.sleep(0.01)
    assert get_record(GenerationJob, job_id).status == "cancelled"
    assert json.dumps(parameters) == original


def test_crashed_job_marked_interrupted(isolated_store, audio_parameters):
    create_job(
        id="interrupted",
        parameters=json.dumps({"audio": audio_parameters}),
        status="running",
        stage="TTS",
        cancel_requested=False,
    )
    recover_interrupted_jobs()
    assert get_record(GenerationJob, "interrupted").status == "interrupted"
