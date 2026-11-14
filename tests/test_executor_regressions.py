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


@pytest.mark.parametrize(
    "code",
    [
        "f = lambda a, /, b=2, *rest, c=3, **extra: [a, b, rest, c, extra]\nprint(f(1, 4, 5, c=6, other=7))",
        "x=4\nf = lambda a=x: a\nx=9\nprint(f())",
        "f = lambda a: a\nprint(f(a=8))",
    ],
)
def test_bind_lambda_arguments_with_python_semantics(code):
    assert_python_output(code)


def test_bind_lambda_arguments_with_python_semantics_rejects_missing():
    with pytest.raises(Exception, match="missing"):
        evaluate_python_code("a=9\nf=lambda a: a\nf()", static_tools=BASE_PYTHON_TOOLS, timeout_seconds=None)


@pytest.mark.parametrize("expression", ["[0, *items, 3]", "(0, *items, 3)", "{0, *items, 3}"])
def test_expand_starred_collection_elements(expression):
    assert_python_output("items = [1, 2]\nprint(" + expression + ")")


@pytest.mark.parametrize(
    "assignment",
    [
        'a, b = "hi"',
        "[a, b] = (1, 2)",
        "a, *middle, b = range(5)",
        "(a, [b, *rest]) = (1, [2, 3, 4])",
    ],
)
def test_unpack_assignment_targets_as_python_sequences(assignment):
    assert_python_output(assignment + "\nprint(a, b)")


def test_unpack_assignment_targets_as_python_sequences_keeps_starred_values():
    assert_python_output("a, *middle, b = range(5)\nprint(a, middle, b)")


def test_clear_except_handler_bindings():
    assert_python_output(
        'error = "old"\ntry:\n    raise ValueError("failure")\nexcept ValueError as error:\n    print(str(error))\ntry:\n    print(error)\nexcept Exception:\n    print("unbound")'
    )


def test_respect_print_options_and_streams():
    assert_python_output('print("a", "b", sep="|", end="!")\nprint("next", sep=None, end=None)')


def test_respect_print_options_and_streams_validates_options():
    with pytest.raises(Exception, match="sep must be None or a string"):
        evaluate_python_code("print(1, sep=3)", static_tools=BASE_PYTHON_TOOLS, timeout_seconds=None)


@pytest.mark.parametrize(
    "expression",
    [
        "[lambda: i for i in range(3)]",
        "[value for i in range(2) for value in [lambda: i]]",
    ],
)
def test_share_comprehension_scope_across_iterations(expression):
    assert_python_output("i = 99\nfuncs = " + expression + "\nprint([f() for f in funcs], i)")


@pytest.mark.parametrize(
    "code",
    [
        "print(list((i, j) for i in range(2) for j in range(i, 3)))",
        "values=[1, 2]\ngen=(x for x in values)\nvalues=[8]\nprint(list(gen))",
        'events=[]\ndef source():\n    events.append("source")\n    return [1, 2]\ngen=(x for x in source())\nprint(events)\nprint(list(gen))',
    ],
)
def test_evaluate_nested_generators_and_capture_outer_iterator(code):
    assert_python_output(code)


def test_resolve_dotted_imports_to_their_root_module():
    state = {}
    evaluate_python_code(
        "import collections.abc\nprint(isinstance({}, collections.abc.Mapping))",
        static_tools=BASE_PYTHON_TOOLS,
        state=state,
        authorized_imports=["collections.abc"],
        timeout_seconds=None,
    )
    assert str(state["_print_outputs"]) == "True\n"


def test_do_not_replace_undefined_names_with_similar_variables():
    with pytest.raises(Exception, match="not defined"):
        evaluate_python_code("value = 1\nprint(valeu)", static_tools=BASE_PYTHON_TOOLS, timeout_seconds=None)


@pytest.mark.parametrize("call", ['f(a=1, **{"a": 2})', 'f(**{"a": 1}, **{"a": 2})', 'f(**{"a": 1}, a=2)'])
def test_reject_duplicate_keywords_during_call_unpacking(call):
    with pytest.raises(Exception, match="multiple values"):
        evaluate_python_code(
            "def f(**kwargs):\n    return kwargs\n" + call, static_tools=BASE_PYTHON_TOOLS, timeout_seconds=None
        )


def test_accept_mapping_objects_in_call_unpacking():
    assert_python_output(
        'class Arguments:\n    def keys(self):\n        return ["a"]\n    def __getitem__(self, key):\n        return 7\ndef f(a):\n    return a\nprint(f(**Arguments()))'
    )


@pytest.mark.parametrize("op", ["and", "or"])
def test_skip_truth_testing_the_final_boolean_operand(op):
    first = "True" if op == "and" else "False"
    assert_python_output(
        'class Value:\n    def __bool__(self):\n        print("checked")\n        return True\n    def __str__(self):\n        return "value"\nprint('
        + first
        + " "
        + op
        + " Value())"
    )


def test_short_circuit_chained_comparisons_using_truth_values():
    assert_python_output(
        'class Result:\n    def __bool__(self):\n        print("truth")\n        return False\n    def __str__(self):\n        return "result"\nclass Value:\n    def __lt__(self, other):\n        print("compare")\n        return Result()\nprint(Value() < Value() < Value())'
    )


def test_apply_function_decorators():
    assert_python_output(
        'events=[]\ndef decorate(label):\n    events.append(label)\n    def apply(fn):\n        def wrapped():\n            return label + fn()\n        return wrapped\n    return apply\n@decorate("a")\n@decorate("b")\ndef value():\n    return "c"\nprint(value(), events)'
    )


def test_apply_class_decorators():
    assert_python_output(
        'def decorate(cls):\n    cls.tag = "decorated"\n    return cls\n@decorate\nclass Value:\n    pass\nprint(Value.tag)'
    )


@pytest.mark.parametrize("body", ["return 7", 'raise ValueError("body")'])
def test_unwind_context_managers_on_enter_failure_and_control_flow(body):
    code = (
        'events=[]\nclass Manager:\n    def __enter__(self):\n        events.append("enter")\n        return (1, 2)\n    def __exit__(self, kind, value, tb):\n        events.append(kind is None)\ndef run():\n    with Manager() as (a, b):\n        '
        + body
        + '\ntry:\n    print(run())\nexcept ValueError:\n    print("caught")\nprint(events)'
    )
    assert_python_output(code)


def test_unwind_context_managers_on_enter_failure_and_control_flow_enter_failure():
    assert_python_output(
        'events=[]\nclass Manager:\n    def __enter__(self):\n        return self\n    def __exit__(self, kind, value, tb):\n        events.append("exit")\nclass Broken:\n    def __enter__(self):\n        raise ValueError("enter")\n    def __exit__(self, kind, value, tb):\n        events.append("broken-exit")\ntry:\n    with Manager(), Broken():\n        pass\nexcept ValueError:\n    print(events)'
    )


def test_evaluate_augmented_assignment_targets_once():
    assert_python_output(
        'events=[]\nitems=[[1]]\ndef select():\n    events.append("object")\n    return items\ndef index():\n    events.append("key")\n    return 0\nselect()[index()] += [2]\nprint(items, events)'
    )


def test_bind_function_definitions_in_the_active_namespace():
    assert_python_output("value = 1\ndef value():\n    return 7\nprint(value())")


def test_support_assignment_expressions():
    assert_python_output("if (count := 3):\n    print(count)\nprint((count := count + 1))")


def test_raise_attributeerror_when_getattr_has_no_default():
    assert_python_output(
        'try:\n    getattr(1, "missing")\nexcept AttributeError:\n    print("missing")\nprint(getattr(1, "missing", None))'
    )


def test_isolate_class_namespaces_and_method_globals():
    assert_python_output(
        'x=1\nclass Value:\n    x=2\n    y=x+3\n    def method(self):\n        return x\nprint(Value.y, Value().method())\ntry:\n    method\nexcept Exception:\n    print("no leaked method")'
    )


def test_resolve_print_aliases_without_hijacking_methods():
    assert_python_output(
        'write = print\nwrite("alias")\nclass Printer:\n    def print(self, value):\n        return "method:" + value\nprint(Printer().print("ok"))'
    )


def test_evaluate_subscript_objects_before_indices():
    assert_python_output(
        'events=[]\ndef collection():\n    events.append("object")\n    return [9]\ndef index():\n    events.append("index")\n    return 0\nprint(collection()[index()], events)'
    )


def test_delete_nested_assignment_target_sequences():
    assert_python_output(
        'a=1\nb=2\ndel (a, [b])\ntry:\n    print(a)\nexcept Exception:\n    print("a missing")\ntry:\n    print(b)\nexcept Exception:\n    print("b missing")'
    )
