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


@pytest.mark.parametrize("items", ["[]", "[1, 2]"])
def test_execute_for_else_without_break(items):
    assert_python_output("for item in " + items + ':\n    print(item)\nelse:\n    print("complete")')


def test_execute_for_else_without_break_respects_break():
    assert_python_output('for item in [1, 2]:\n    break\nelse:\n    print("complete")')


@pytest.mark.parametrize("initial", [0, 2])
def test_execute_while_else_without_break(initial):
    assert_python_output("n = " + str(initial) + '\nwhile n:\n    n -= 1\nelse:\n    print("complete")')


def test_execute_while_else_without_break_respects_break():
    assert_python_output('while True:\n    break\nelse:\n    print("complete")')


@pytest.mark.parametrize("statement", ["return 7", "break", "continue"])
def test_keep_control_flow_out_of_exception_handlers(statement):
    body = (
        "def run():\n    for i in [1]:\n        try:\n            "
        + statement
        + '\n        except Exception:\n            print("caught")\n        finally:\n            print("finally")\n    return 9\nprint(run())'
    )
    assert_python_output(body)
