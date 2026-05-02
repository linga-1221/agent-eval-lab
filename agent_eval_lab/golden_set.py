"""Golden set: hand-curated functions for evaluating agent output quality."""

GOLDEN_SET = [
    {
        "name": "add_two_numbers",
        "code": "def add(a: int, b: int) -> int:\n    return a + b",
        "expected_edge_cases": ["negative numbers", "zero", "large numbers"],
        "min_tests": 3,
    },
    {
        "name": "is_palindrome",
        "code": "def is_palindrome(s: str) -> bool:\n    s = s.lower().replace(' ', '')\n    return s == s[::-1]",
        "expected_edge_cases": ["empty string", "single char", "case sensitivity", "spaces"],
        "min_tests": 4,
    },
    {
        "name": "fibonacci",
        "code": "def fib(n: int) -> int:\n    if n <= 1:\n        return n\n    return fib(n-1) + fib(n-2)",
        "expected_edge_cases": ["n=0", "n=1", "negative n", "large n"],
        "min_tests": 4,
    },
    {
        "name": "divide",
        "code": "def divide(a: float, b: float) -> float:\n    return a / b",
        "expected_edge_cases": ["division by zero", "negative", "float precision"],
        "min_tests": 3,
    },
    {
        "name": "reverse_list",
        "code": "def reverse_list(lst: list) -> list:\n    return lst[::-1]",
        "expected_edge_cases": ["empty list", "single element", "mixed types"],
        "min_tests": 3,
    },
    {
        "name": "count_vowels",
        "code": "def count_vowels(s: str) -> int:\n    return sum(1 for c in s.lower() if c in 'aeiou')",
        "expected_edge_cases": ["empty string", "no vowels", "all vowels", "uppercase"],
        "min_tests": 4,
    },
    {
        "name": "factorial",
        "code": "def factorial(n: int) -> int:\n    if n < 0:\n        raise ValueError('negative')\n    if n == 0:\n        return 1\n    return n * factorial(n-1)",
        "expected_edge_cases": ["n=0", "n=1", "negative", "large n"],
        "min_tests": 4,
    },
    {
        "name": "find_max",
        "code": "def find_max(lst: list) -> int:\n    if not lst:\n        raise ValueError('empty')\n    return max(lst)",
        "expected_edge_cases": ["empty list", "single element", "duplicates", "negative"],
        "min_tests": 4,
    },
    {
        "name": "is_prime",
        "code": "def is_prime(n: int) -> bool:\n    if n < 2:\n        return False\n    for i in range(2, int(n**0.5)+1):\n        if n % i == 0:\n            return False\n    return True",
        "expected_edge_cases": ["n=0", "n=1", "n=2", "negative", "large prime"],
        "min_tests": 5,
    },
    {
        "name": "string_to_int",
        "code": "def to_int(s: str) -> int:\n    return int(s.strip())",
        "expected_edge_cases": ["whitespace", "negative", "invalid string", "empty"],
        "min_tests": 4,
    },
    {
        "name": "sum_list",
        "code": "def sum_list(lst: list) -> int:\n    return sum(lst)",
        "expected_edge_cases": ["empty list", "single element", "negative numbers"],
        "min_tests": 3,
    },
    {
        "name": "is_even",
        "code": "def is_even(n: int) -> bool:\n    return n % 2 == 0",
        "expected_edge_cases": ["zero", "negative", "large number"],
        "min_tests": 3,
    },
    {
        "name": "celsius_to_fahrenheit",
        "code": "def c_to_f(c: float) -> float:\n    return c * 9/5 + 32",
        "expected_edge_cases": ["zero", "negative", "boiling point", "freezing point"],
        "min_tests": 4,
    },
    {
        "name": "remove_duplicates",
        "code": "def dedupe(lst: list) -> list:\n    return list(dict.fromkeys(lst))",
        "expected_edge_cases": ["empty list", "all unique", "all duplicates", "preserves order"],
        "min_tests": 4,
    },
    {
        "name": "word_count",
        "code": "def word_count(s: str) -> int:\n    return len(s.split())",
        "expected_edge_cases": ["empty string", "single word", "multiple spaces", "newlines"],
        "min_tests": 4,
    },
]
