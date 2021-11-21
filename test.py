from unittest import TestCase

import re
from A2B import parse, execute

class Test1(TestCase):
    def test_a2b(self):
        program = '''
            a=b
        '''

        p = parse(program)

        cases = [
            ('abc', 'bbc'),
            ('aab', 'bbb'),
            ('aabbac', 'bbbbbc'),
        ]

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))

    def test_singleton(self):
        program = '''
            aa=a
            bb=b
            cc=c
        '''

        p = parse(program)

        input_list = [
            'aaaabbcccc',
            'abccc',
            'cccbba'
        ]

        cases = []

        for input_data in input_list:
            expected = re.sub(r"(.)\1+", r"\1", input_data)
            cases.append((input_data, expected))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))

    def test_sort(self):
        input_list = [
            "a",
            "aa",
            "bab",
            "cacb",
            "bbacc",
            "aabcba",
            "cacbccc",
            "bbbbbacc",
            "bacbabaca",
            "ccaacbaaaa",
        ]

        program = '''
            ba=ab
            ca=ac
            cb=bc
        '''

        p = parse(program)

        cases = []

        for input_data in input_list:
            expected = ''.join(sorted(input_data))
            cases.append((input_data, expected))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))

    def test_compare(self):
        input_list = [
            "ababbbabbb",
            "abb",
            "abbbb",
            "ababbabbbb",
            "baaab",
            "aababbbbbb",
            "bbbaaaabaaa",
            "bbaaabaa",
            "baabbaabbaa",
            "baabaaaa",
            "bbaaaabab",
            "abaaaabbbabab",
            "bbbbbabaaa",
            "bbabababa",
            "aabaabab",
            "baaaab",
            "abaaaaaa",
            "bbabaaa",
            "babababbb",
            "abbaa",
            "a",
            "aa",
            "bbbbb",
        ]

        program = '''
            ba=ab
            ab=
            aa=a
            bb=b
        '''

        p = parse(program)

        cases = []

        for input_data in input_list:
            expected = sorted(input_data)[len(input_data) / 2]
            cases.append((input_data, expected))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))

