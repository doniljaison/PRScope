import uuid

from app.workers.tasks import analyze_pr_task

def test_analyze_pr_task(mocker):
    # This is a synchronous test because Celery tasks run synchronously in the worker.
    # We mock time.sleep so the test runs instantly.
    mock_sleep = mocker.patch("time.sleep")
    
    pr_id = str(uuid.uuid4())
    result = analyze_pr_task(pr_id)
    
    # Assert the mock was called
    mock_sleep.assert_called_once_with(3)
    
    # Assert the returned dictionary
    assert result["status"] == "success"
    assert result["pr_id"] == pr_id
