import app.main as main_module


def test_job_progress_never_moves_backwards(monkeypatch):
    persisted = []

    def fake_persist(job_id, **values):
        persisted.append((job_id, values))

    monkeypatch.setattr(
        main_module,
        "_persist_job_update",
        fake_persist,
    )

    job_id = "monotonic-progress-job"
    main_module.JOB_CACHE.pop(job_id, None)

    main_module._job_update(
        job_id,
        progress=35,
        message="Reviewing chapter sections",
    )
    main_module._job_update(
        job_id,
        progress=22,
        message="Preparing an earlier stage",
    )

    job = main_module.JOB_CACHE[job_id]
    assert job["progress"] == 35
    assert job["message"] == "Reviewing chapter sections"
    assert persisted[-1][1]["progress"] == 35
    assert persisted[-1][1]["message"] is None

    main_module._job_update(
        job_id,
        progress=54,
        message="Completing section coverage",
    )
    assert main_module.JOB_CACHE[job_id]["progress"] == 54
    assert (
        main_module.JOB_CACHE[job_id]["message"]
        == "Completing section coverage"
    )

    main_module.JOB_CACHE.pop(job_id, None)


def test_equal_progress_may_update_the_message(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "_persist_job_update",
        lambda *args, **kwargs: None,
    )

    job_id = "same-progress-message-job"
    main_module.JOB_CACHE.pop(job_id, None)

    main_module._job_update(
        job_id,
        progress=90,
        message="Assessing findings",
    )
    main_module._job_update(
        job_id,
        progress=90,
        message="Validating findings",
    )

    assert main_module.JOB_CACHE[job_id]["progress"] == 90
    assert main_module.JOB_CACHE[job_id]["message"] == "Validating findings"

    main_module.JOB_CACHE.pop(job_id, None)
