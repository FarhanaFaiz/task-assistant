from types import SimpleNamespace

from app.agent.service import extract_final_text


def part(*, text=None, function_call=None, function_response=None):
    return SimpleNamespace(
        text=text,
        function_call=function_call,
        function_response=function_response,
    )


def event(*parts, error_code=None, error_message=None):
    return SimpleNamespace(
        content=SimpleNamespace(parts=list(parts)),
        error_code=error_code,
        error_message=error_message,
    )


def test_extracts_final_text_after_tool_execution():
    events = [
        event(part(function_call=SimpleNamespace(name="list_tasks", args={}))),
        event(part(function_response=SimpleNamespace(response={"result": []}))),
        event(part(text="You have no pending tasks.")),
    ]

    assert extract_final_text(events) == "You have no pending tasks."


def test_handles_task_mode_finish_task_without_text():
    events = [
        event(
            part(
                function_call=SimpleNamespace(
                    name="finish_task",
                    args={"result": "Task added successfully."},
                )
            )
        )
    ]

    assert extract_final_text(events) == "Task added successfully."
