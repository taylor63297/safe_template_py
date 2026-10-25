"""Tests for safe_template_py.core.

Every assertion here corresponds to behaviour the implementation actually
claims to support.  We do not test filters, loops, or attribute access
because the library does not implement them.
"""

import unittest

from safe_template_py import (
    SafeTemplate,
    render_string,
    SafeTemplateError,
    MissingVariable,
)


class TestBasicSubstitution(unittest.TestCase):

    def test_single_placeholder(self):
        self.assertEqual(render_string("{{x}}", {"x": "hi"}), "hi")

    def test_placeholder_with_spaces(self):
        self.assertEqual(render_string("{{ x }}", {"x": "hi"}), "hi")

    def test_placeholder_with_tabs(self):
        self.assertEqual(render_string("{{\tx\t}}", {"x": "hi"}), "hi")

    def test_multiple_placeholders(self):
        out = render_string("{{a}}-{{b}}-{{a}}", {"a": "1", "b": "2"})
        self.assertEqual(out, "1-2-1")

    def test_text_around_placeholders(self):
        out = render_string("Hello {{name}}!", {"name": "world"})
        self.assertEqual(out, "Hello world!")

    def test_no_placeholders(self):
        self.assertEqual(render_string("plain text", {}), "plain text")

    def test_empty_template(self):
        self.assertEqual(render_string("", {}), "")


class TestValueConversion(unittest.TestCase):

    def test_int_value(self):
        self.assertEqual(render_string("n={{n}}", {"n": 42}), "n=42")

    def test_float_value(self):
        # We compare the string representation, not the float with ==.
        self.assertEqual(render_string("{{x}}", {"x": 1.5}), "1.5")

    def test_none_value(self):
        # str(None) == "None"; we stringify exactly once and do not special-case None.
        self.assertEqual(render_string("{{x}}", {"x": None}), "None")

    def test_bool_value(self):
        self.assertEqual(render_string("{{x}}", {"x": True}), "True")

    def test_list_value(self):
        self.assertEqual(render_string("{{x}}", {"x": [1, 2]}), "[1, 2]")


class TestMissingVariables(unittest.TestCase):

    def test_raise_by_default(self):
        with self.assertRaises(MissingVariable):
            render_string("{{x}}", {})

    def test_raise_is_subclass_of_base(self):
        # MissingVariable must be catchable as SafeTemplateError too.
        with self.assertRaises(SafeTemplateError):
            render_string("{{x}}", {})

    def test_keep_leaves_token(self):
        out = render_string("{{x}}", {}, missing=SafeTemplate.KEEP)
        self.assertEqual(out, "{{ x }}")

    def test_blank_substitutes_empty(self):
        out = render_string("a{{x}}b", {}, missing=SafeTemplate.BLANK)
        self.assertEqual(out, "ab")

    def test_callable_missing(self):
        out = render_string("{{x}}", {}, missing=lambda n: f"<{n}>")
        self.assertEqual(out, "<x>")

    def test_callable_missing_stringified(self):
        # A callable that returns a non-string should be stringified.
        out = render_string("{{x}}", {}, missing=lambda n: 99)
        self.assertEqual(out, "99")


class TestSyntaxErrors(unittest.TestCase):

    def test_attribute_access_rejected(self):
        with self.assertRaises(SyntaxError):
            SafeTemplate("{{a.b}}")

    def test_dash_in_name_rejected(self):
        with self.assertRaises(SyntaxError):
            SafeTemplate("{{a-b}}")

    def test_empty_braces_rejected(self):
        with self.assertRaises(SyntaxError):
            SafeTemplate("{{ }}")

    def test_bad_placeholder_between_good_ones(self):
        with self.assertRaises(SyntaxError):
            SafeTemplate("{{a}} and {{a.b}} and {{c}}")


class TestTypeChecks(unittest.TestCase):

    def test_non_string_source(self):
        with self.assertRaises(TypeError):
            SafeTemplate(123)  # type: ignore[arg-type]

    def test_non_mapping_variables(self):
        tpl = SafeTemplate("{{x}}")
        with self.assertRaises(TypeError):
            tpl.render([("x", "1")])  # type: ignore[arg-type]


class TestReuseAndStructure(unittest.TestCase):

    def test_compiled_template_reusable(self):
        tpl = SafeTemplate("Hi {{name}}")
        self.assertEqual(tpl.render({"name": "a"}), "Hi a")
        self.assertEqual(tpl.render({"name": "b"}), "Hi b")

    def test_literal_with_braces_that_are_not_placeholder(self):
        # Single braces are not placeholders and must pass through untouched.
        out = render_string("function() { return {{x}}; }", {"x": "42"})
        self.assertEqual(out, "function() { return 42; }")

    def test_repr_contains_source(self):
        tpl = SafeTemplate("{{x}}")
        self.assertIn("{{x}}", repr(tpl))


if __name__ == "__main__":
    unittest.main()
