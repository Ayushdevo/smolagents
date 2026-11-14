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


def test_support_bare_reraise_in_exception_handlers():
    assert_python_output(
        'try:\n    try:\n        raise ValueError("original")\n    except ValueError:\n        raise\nexcept ValueError as error:\n    print(str(error))'
    )


def test_delete_object_attributes():
    assert_python_output(
        'class Box:\n    pass\nbox = Box()\nbox.value = 3\ndel box.value\nprint(hasattr(box, "value"))'
    )


@pytest.mark.parametrize("value", ["(2, 3)", "range(2, 4)", "'bc'"])
def test_allow_iterables_in_list_augmented_assignment(value):
    assert_python_output("items = [1]\nalias = items\nitems += " + value + "\nprint(items, alias is items)")


def test_reject_undefined_augmented_assignment_targets():
    with pytest.raises(Exception, match="not defined"):
        evaluate_python_code("missing += 1", static_tools=BASE_PYTHON_TOOLS, timeout_seconds=None)


@pytest.mark.parametrize(
    "code",
    [
        "def f(a, /, b=2, *rest, c=3, **extra):\n    return [a, b, rest, c, extra]\nprint(f(1, 4, 5, 6, c=7, other=8))",
        "x=9\ndef f(x=2):\n    return x\nprint(f())",
        "x=1\ndef f(a=x):\n    return a\nx=8\nprint(f())",
        "def f(values=[]):\n    values.append(1)\n    return len(values)\nprint(f(), f())",
    ],
)
def test_bind_function_arguments_with_python_semantics(code):
    assert_python_output(code)


@pytest.mark.parametrize("call", ["f()", "f(1, 2, 3)", "f(1, a=2)", "f(1, unknown=2)"])
def test_bind_function_arguments_with_python_semantics_rejects_invalid_calls(call):
    with pytest.raises(Exception, match="(missing|too many|multiple values|unexpected keyword)"):
        evaluate_python_code(
            "a=99\ndef f(a, b=2):\n    return a\n" + call, static_tools=BASE_PYTHON_TOOLS, timeout_seconds=None
        )
