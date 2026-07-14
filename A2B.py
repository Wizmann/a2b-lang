#!/usr/bin/env python3

import sys
import argparse

KEYWORD_ONCE = 'once'
KEYWORD_START = 'start'
KEYWORD_RETURN = 'return'
KEYWORD_END = 'end'
KEYWORD_NONE = None

EXECUTED_NONE = 'none'
EXECUTED_DONE = 'done'
EXECUTED_RETURN = 'return'
EXECUTED_PASS = 'pass'

LINE_LENGTH_LIMIT = 1000
# The language itself does not prescribe a small execution-step limit.  A high
# guard remains to stop non-terminating programs without rejecting valid
# algorithms for the bundled bounded arithmetic tasks.
EXECUTOR_OPERATION_LIMIT = 1000000

class A2BParseException(Exception):
    def __init__(self, line_no, description):
        self.message = '[Syntax Error on L%d]: %s' % (line_no + 1, description)
        super().__init__(self.message)

class A2BExecutionException(Exception):
    def __init__(self, description):
        self.message = '[Runtime Error]: %s' % (description)
        super().__init__(self.message)

class Program(object):
    def __init__(self, exprs):
        self.exprs = list(exprs)

class Expression(object):
    def __init__(self, line_no, plain_text, left, right):
        self.line_no = line_no
        self.plain_text = plain_text
        self.left = left
        self.right = right
        self.executed = 0

    def Execute(self, input_data):
        if self.left.keyword == KEYWORD_ONCE and self.executed:
            return EXECUTED_PASS, ''
        if not self.left.match(input_data):
            return EXECUTED_PASS, ''
        self.executed += 1
        result = self.left.replace(input_data, self.right)
        if self.right.keyword == KEYWORD_RETURN:
            return EXECUTED_RETURN, result
        return EXECUTED_DONE, result

class Pattern(object):
    def __init__(self, keyword, pattern):
        self.keyword = keyword
        self.pattern = pattern

    def get_pattern(self):
        return self.pattern

    def match(self, input_data):
        if self.keyword == KEYWORD_START:
            return input_data.startswith(self.pattern)
        if self.keyword == KEYWORD_END:
            return input_data.endswith(self.pattern)
        return self.pattern in input_data

    def match_span(self, input_data):
        if self.keyword == KEYWORD_START:
            return 0, len(self.pattern)
        if self.keyword == KEYWORD_END:
            return len(input_data) - len(self.pattern), len(input_data)

        start = input_data.find(self.pattern)
        return start, start + len(self.pattern)

    def replace(self, input_data, other):
        assert self.match(input_data)
        start, end = self.match_span(input_data)

        if other.keyword == KEYWORD_RETURN:
            return other.pattern

        before = input_data[:start]
        after = input_data[end:]
        if other.keyword == KEYWORD_START:
            return other.pattern + before + after
        if other.keyword == KEYWORD_END:
            return before + after + other.pattern
        return before + other.pattern + after

    @staticmethod
    def _is_ascii(value):
        return all(ord(char) < 128 for char in value)

    @staticmethod
    def Parse(line_no, input_data):
        keyword = KEYWORD_NONE
        pattern = input_data

        if input_data.startswith('('):
            keyword_end = input_data.find(')')
            if keyword_end < 0:
                raise A2BParseException(line_no, 'Invalid pattern "%s"' % input_data)
            keyword = input_data[1:keyword_end]
            pattern = input_data[keyword_end + 1:]

        if keyword not in [KEYWORD_NONE, KEYWORD_START, KEYWORD_END,
                           KEYWORD_RETURN, KEYWORD_ONCE]:
            raise A2BParseException(line_no, 'Invalid keyword "(%s)"' % keyword)

        if (not Pattern._is_ascii(pattern) or
                any(char in '=#()' for char in pattern)):
            raise A2BParseException(line_no, 'Invalid pattern "%s"' % input_data)

        return Pattern(keyword, pattern)

def parse(program):
    lines = program.split("\n")

    p = Program([])
    commented_flag = False
    for line_no, line in enumerate(lines):
        if line.endswith('\r'):
            line = line[:-1]
        if line == '':
            continue

        comment_line = line.strip()
        if commented_flag and comment_line.endswith('*/'):
            commented_flag = False
            continue

        if commented_flag:
            continue

        if comment_line.startswith('/*'):
            commented_flag = True
            continue

        if line.count('=') != 1:
            raise A2BParseException(line_no, 'Each line should have one and only one "="')
        left, right = (Pattern.Parse(line_no, value) for value in line.split('='))
        if left.keyword == KEYWORD_RETURN:
            raise A2BParseException(line_no, "Keyword(return) can't be placed on the left side of an expression")
        if right.keyword == KEYWORD_ONCE:
            raise A2BParseException(line_no, "Keyword(once) can't be placed on the right side of an expression")
        e = Expression(line_no, line, left, right)
        p.exprs.append(e)

    return p

def printable_format(line):
    return line

def execute(program, line, verbose=False):
    if not Pattern._is_ascii(line) or '\n' in line or '\r' in line:
        raise A2BExecutionException("Input must be one line of ASCII text")
    if len(line) > LINE_LENGTH_LIMIT:
        raise A2BExecutionException("String Length Limit Exceeded")

    operation_counter = 0

    for expr in program.exprs:
        expr.executed = 0

    while True:
        executed = EXECUTED_NONE
        for expr in program.exprs:
            executed, output = expr.Execute(line)
            if executed in [EXECUTED_DONE, EXECUTED_RETURN]:
                operation_counter += 1
                if verbose:
                    print('Step %d:' % operation_counter, file=sys.stderr)
                    print('  L%d: %s' % (expr.line_no + 1, expr.plain_text), file=sys.stderr)
                    print('>> %s' % printable_format(line), file=sys.stderr)
                    print('<< %s%s' % (
                        '(return)' if executed == EXECUTED_RETURN else '',
                        printable_format(output)), file=sys.stderr)
                    print('', file=sys.stderr)
                line = output
                break
        else:
            break
        
        if operation_counter > EXECUTOR_OPERATION_LIMIT:
            raise A2BExecutionException("Time Limit Exceeded")

        if len(line) > LINE_LENGTH_LIMIT:
            raise A2BExecutionException("String Length Limit Exceeded")

        if executed == EXECUTED_RETURN:
            break

    return printable_format(line)

if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description='A2B lang interpreter')
    argparser.add_argument('-v', '--verbose', dest='verbose', action='store_true')
    argparser.add_argument('filename')
    argparser.set_defaults(verbose=False)
    args = argparser.parse_args()

    with open(args.filename, encoding='utf-8') as input_file:
        plain_text = input_file.read()
        program = parse(plain_text)

    line = input()
    result = execute(program, line, args.verbose)
    print(result)
