"""Tests for demo-app calculator"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from main import add, subtract, multiply, divide, power


class TestAdd:
    def test_positive(self):
        assert add(2, 3) == 5

    def test_negative(self):
        assert add(-1, -1) == -2

    def test_zero(self):
        assert add(0, 5) == 5


class TestSubtract:
    def test_basic(self):
        assert subtract(10, 3) == 7

    def test_negative_result(self):
        assert subtract(3, 10) == -7


class TestMultiply:
    def test_basic(self):
        assert multiply(4, 5) == 20

    def test_by_zero(self):
        assert multiply(100, 0) == 0


class TestDivide:
    def test_basic(self):
        assert divide(10, 2) == 5

    def test_by_zero(self):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            divide(10, 0)


class TestPower:
    def test_basic(self):
        assert power(2, 3) == 8

    def test_zero_exp(self):
        assert power(5, 0) == 1
