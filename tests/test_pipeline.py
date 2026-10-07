"""The pipeline stops at the first failing step and returns a non-zero exit code."""

from mandipulse import pipeline


def test_pipeline_stops_and_fails_on_first_error(monkeypatch, tmp_path):
    ran = []
    monkeypatch.setattr(pipeline, "LOG_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "step_load", lambda glob: ran.append("load"))
    monkeypatch.setattr(pipeline, "step_ml_schema", lambda: ran.append("schema"))

    def broken_dbt(*args):
        ran.append("dbt")
        raise pipeline.StepFailed("dbt build exited with code 1")

    monkeypatch.setattr(pipeline, "_dbt", broken_dbt)
    monkeypatch.setattr(pipeline, "step_export", lambda snapshot: ran.append("export"))

    assert pipeline.run_pipeline(skip_ml=True) == 1
    assert ran == ["load", "schema", "dbt"]  # export never ran
    log = next(tmp_path.glob("pipeline_*.log")).read_text(encoding="utf-8")
    assert "FAILED" in log and "dbt build exited with code 1" in log


def test_pipeline_success_runs_every_step(monkeypatch, tmp_path):
    ran = []
    monkeypatch.setattr(pipeline, "LOG_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "step_load", lambda glob: ran.append("load"))
    monkeypatch.setattr(pipeline, "step_ml_schema", lambda: ran.append("schema"))
    monkeypatch.setattr(pipeline, "_dbt", lambda *a: ran.append("dbt " + " ".join(a)))
    monkeypatch.setattr(pipeline, "step_score", lambda: ran.append("score"))
    monkeypatch.setattr(pipeline, "step_export", lambda snapshot: ran.append("export"))

    assert pipeline.run_pipeline() == 0
    assert ran == ["load", "schema", "dbt build", "score", "dbt test --select source:ml", "export"]
