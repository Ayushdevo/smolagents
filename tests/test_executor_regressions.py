import contextlib
import io

import pytest

from smolagents.local_python_executor import BASE_PYTHON_TOOLS, evaluate_python_code


def assert_python_output(code):
    expected = io.StringIO()
    with contextlib.redirect_stdout(expected):
        exec(compile(code, "<regression>", "exec"), {})
    state = {}
    evaluate_python_code(code, static_tools=BASE_PYTHON_TOOLS, state=state, timeout_seconds=None)
    assert str(state["_print_outputs"]) == expected.getvalue()


@pytest.mark.parametrize("conversion", ["s", "r", "a"])
def test_honor_fstring_conversions(conversion):
    assert_python_output("value = 'café'\nprint(f'{value!" + conversion + ":>12}')")


@pytest.mark.parametrize("body", ["value = 7", "7", "if True:\n        7"])
def test_return_none_without_explicit_return(body):
    assert_python_output("def calculate():\n    " + body + "\nprint(calculate())")


def test_evaluate_dictionary_entries_in_order():
    assert_python_output(
        "events = []\ndef record(x):\n    events.append(x)\n    return x\nvalue = {record('k1'): record('v1'), record('k2'): record('v2')}\nprint(events)"
    )


def test_evaluate_dictionary_entries_in_order_with_unpacking():
    assert_python_output("first = {'a': 1, 'b': 2}\nprint({**first, 'b': 3, **{'c': 4}})")
