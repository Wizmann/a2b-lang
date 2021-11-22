from unittest import TestCase

import re
from A2B import parse, execute
from collections import Counter

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

class Test2(TestCase):
    def test_hello_world(self):
        input_list = [
            "abc",
            "a",
            "",
            "c"
        ]

        program = '''
            =(return)helloworld
        '''

        p = parse(program)

        for input_data in input_list:
            self.assertEqual('helloworld', execute(p, input_data))

    def test_aaa(self):
        input_list = [
            "aaaaa",
            "aaa",
            "aabbba",
            "abababababcc!!!"
        ]

        program = '''
            aaa=(return)true
            b=
            c=
            =(return)false
        '''

        p = parse(program)

        cases = []
        for input_data in input_list:
            if 'aaa' in input_data.replace('b', '').replace('c', ''):
                cases.append((input_data, "true"))
            else:
                cases.append((input_data, "false"))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))


    def test_odd(self):
        input_list = [
            "abc",
            "ab",
            "aabbba",
            "abababababcc"
        ]

        program = '''
            ba=ab
            ca=ac
            cb=bc
            aaa=a
            bbb=b
            ccc=c
            aa=(return)false
            bb=(return)false
            cc=(return)false
            =(return)true
        '''

        p = parse(program)

        cases = []
        for input_data in input_list:
            c = Counter(input_data)
            for value in c.values():
                if value != 0 and value % 2 == 0:
                    cases.append((input_data, "false"))
                    break
            else:
                cases.append((input_data, "true"))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))

    def test_least(self):
        input_list = [
            "aacbbaaa",
            "aacbaabbaa",
            "babaacaaaba",
            "accccacb",
            "bcaacacaa",
            "bbcbabbbcc",
            "cacabcccbbaaaacc",
            "abbbaccbcbccbcb",
            "bbaccbbbcab",
            "bbbcbcbbab",
            "abaababca",
            "ccbcabbbab",
            "bccabcbccbbc",
            "cccbabcccaaaaac",
            "bbcaaaaaa",
            "accbcbbbcbbccc",
            "abbbbacabacbb",
            "bccbbcacc",
            "cacbacccc",
            "bccacbbccbcaaba",
        ]

        program = '''
            ba=ab
            ca=ac
            cb=bc
            ab=x
            xb=bx
            xc=
            bc=(return)a
            x=(return)c
            ac=(return)b
        '''

        p = parse(program)

        cases = []
        for input_data in input_list:
            c = Counter(input_data)
            result = sorted(c.items(), key=lambda x: x[1])[0][0]
            cases.append((input_data, result))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))

class Test3(TestCase):
    def test_remove(self):
        input_list = [
            "aacbbaaa",
            "aacbaabbaa",
            "babaacaaaba",
            "accccacb",
            "bcaacacaa",
            "bbcbabbbcc",
            "cacabcccbbaaaacc",
            "abbbaccbcbccbcb",
            "bbaccbbbcab",
            "bbbcbcbbab",
            "abaababca",
            "ccbcabbbab",
            "bccabcbccbbc",
            "cccbabcccaaaaac",
            "bbcaaaaaa",
            "accbcbbbcbbccc",
            "abbbbacabacbb",
            "bccbbcacc",
            "cacbacccc",
            "bccacbbccbcaaba",
            "aaaaa",
            "abaaaba",
            "bababacccaa",
        ]

        program = '''
            (start)a=
            (end)a=
        '''

        p = parse(program)

        cases = []
        for input_data in input_list:
            result = re.sub('^a+|a+$', '', input_data)
            cases.append((input_data, result))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))

    def test_palindrome(self):
        input_list = [
            "accaccacca",
            "bbabaababb",
            "ccacaacacc",
            "bbcbaaaabcbb",
            "caccac",
            "bbccbbccbb",
            "a",
            "b",
            "c",
            "",
            "abcba",
            "cbccbc",
            "abababa",
            "aacaa",
            "cbcacabc",
            "ccbbbcc",
            "acaccca",
            "bbaccbbbcab",
            "bbbcbcbbab",
            "abaababca",
            "ccbcabbbab",
            "bccabcbccbbc",
            "cccbabcccaaaaac",
        ]

        program = '''
            XaX=(return)false
            XbX=(return)false
            XcX=(return)false
            (end)aXa=
            (end)bXb=
            (end)cXc=
            (start)a=(end)Xa
            (start)b=(end)Xb
            (start)c=(end)Xc
            =(return)true
        '''

        p = parse(program)

        cases = []
        for input_data in input_list:
            result = "true" if input_data == input_data[::-1] else "false"
            cases.append((input_data, result))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))

class Test4(TestCase):
    def test_hello2(self):
        input_list = [
            "a",
            "b",
            "c",
            "",
            "abcba",
            "cbccbc",
            "abababa",
            "aacaa",
        ]

        program1 = '''
            (once)=(start)hello
        '''

        program2 = '''
            (once)=hello
        '''

        p1 = parse(program1)
        p2 = parse(program2)

        cases = []
        for input_data in input_list:
            result = "hello" + input_data
            cases.append((input_data, result))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p1, input_data))
            self.assertEqual(expected, execute(p2, input_data))

    def test_reverse(self):
        input_list = [
            "ab",
            "bc",
            "ca",
            "abcba",
            "cbccbc",
            "abababa",
            "aacaa",
            "bbbcbcbbab",
            "abaababca",
            "ccbcabbbab",
            "bccabcbccbbc",
            "cccbabcccaaaaac",
        ]

        program = '''
            (once)=(start)X
            Xa=(end)Ya
            Xb=(end)Yb
            Xc=(end)Yc
            aY=(start)a
            bY=(start)b
            cY=(start)c
        '''

        p = parse(program)

        cases = []
        for input_data in input_list:
            result = list(input_data)
            result[0], result[-1] = result[-1], result[0]
            cases.append((input_data, ''.join(result)))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))

    def test_reverse2(self):
        input_list = [
            "a",
            "b",
            "c",
            "ab",
            "bc",
            "ca",
            "abcba",
            "cbccbc",
            "abababa",
            "aacaa",
            "bbbcbcbbab",
            "abaababca",
            "ccbcabbbab",
            "bccabcbccbbc",
            "cccbabcccaaaaac",
        ]

        program = '''
            (once)=(end)XXXXXXXXXXXXXXXXXXXXXXX
            aX=(end)a
            bX=(end)b
            cX=(end)c
            X=
        '''

        p = parse(program)

        cases = []
        for input_data in input_list:
            result = input_data[::-1]
            cases.append((input_data, result))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p, input_data))

class Test5(TestCase):
    def test_count(self):
        input_list = ['{:b}'.format(i) for i in xrange(1, 64)]

        program1 = '''
            (once)=X
            X1=(start)aX
            X0=(start)X
            Xa=aaX
            X=
        '''

        program2 = '''
            (once)=(end)XYXXYXXXYXXXXYXXXXXYXXXXXXY
            0X=0
            0Y=
            1XY=(start)a
            1XXY=(start)aa
            1XXXY=(start)aaaa
            1XXXXY=(start)aaaaaaaa
            1XXXXXY=(start)aaaaaaaaaaaaaaaa
            1XXXXXXY=(start)aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
            aX=a
            Y=
        '''

        p1 = parse(program1)
        p2 = parse(program2)

        cases = []
        for input_data in input_list:
            result = 'a' * int(input_data, 2)
            cases.append((input_data, result))

        for input_data, expected in cases:
            self.assertEqual(expected, execute(p1, input_data))
            self.assertEqual(expected, execute(p2, input_data))


