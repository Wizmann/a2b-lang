#!/usr/bin/python2
#coding=utf-8
import sys
import re
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

LINE_LENGTH_LIMIT = 512
EXECUTOR_OPERATION_LIMIT = 1024

class A2BParseException(Exception):
    def __init__(self, line_no, description):
        self.message = '[Syntax Error on L%d]: %s' % (line_no + 1, description)
        super(A2BParseException, self).__init__(self.message)

class A2BExecutionException(Exception):
    def __init__(self, description):
        self.message = '[Runtime Error]: %s' % (description)
        super(A2BExecutionException, self).__init__(self.message)

class Program(object):
    def __init__(self, exprs):
        self.exprs = []

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
    pattern_re = re.compile(r'^(\((?P<keyword>\w+?)\))?(?P<pattern>(((?![()^$=])[\x00-\x7F]))*)$')

    def __init__(self, keyword, pattern):
        self.keyword = keyword
        self.pattern = pattern

    def get_pattern(self):
        if self.keyword == KEYWORD_START:
            pattern = '^' + self.pattern
        elif self.keyword == KEYWORD_END:
            pattern = self.pattern + '$'
        else:
            pattern = self.pattern
        return pattern

    def match(self, input_data):
        pattern = self.get_pattern()
        return pattern in input_data

    def replace(self, input_data, other):
        pattern = self.get_pattern()
        assert pattern in input_data

        result = ''

        if other.keyword == KEYWORD_RETURN:
            result = other.pattern
        elif other.keyword == KEYWORD_START:
            result = input_data.replace(pattern, '', 1)
            result = other.pattern + result
        elif other.keyword == KEYWORD_END:
            result = input_data.replace(pattern, '', 1)
            result = result + other.pattern
        else:
            result = input_data.replace(pattern, other.pattern, 1)

        result = result.replace('^', '').replace('$', '')
        result = '^' + result
        result = result + '$'

        return result

    @staticmethod
    def Parse(line_no, input_data):
        match = Pattern.pattern_re.search(input_data)
        if not match:
            raise A2BParseException(line_no, 'Invalid pattern "%s"' % input_data)
        d = match.groupdict()
        if not d:
            raise A2BParseException(line_no, 'Invalid pattern "%s"' % input_data)
        keyword = d.get('keyword', KEYWORD_NONE)
        if keyword not in [KEYWORD_NONE, KEYWORD_START, KEYWORD_END, KEYWORD_RETURN, KEYWORD_ONCE]:
            raise A2BParseException(line_no, 'Invalid keyword "(%s)"' % keyword)

        return Pattern(keyword, d['pattern'])

def parse(program):
    lines = program.split("\n")

    p = Program([])
    commented_flag = False
    for line_no, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue

        if commented_flag and line.endswith('*/'):
            commented_flag = False
            continue

        if commented_flag:
            continue

        if line.startswith('/*'):
            commented_flag = True
            continue

        if line.count('=') != 1:
            raise A2BParseException(line_no, 'Each line should have one and only one "="')
        left, right = map(lambda s: Pattern.Parse(line_no, s.strip()), line.split('='))
        if left.keyword == KEYWORD_RETURN:
            raise A2BParseException(line_no, "Keyword(return) can't be placed on the left side of an expression")
        if right.keyword == KEYWORD_ONCE:
            raise A2BParseException(line_no, "Keyword(once) can't be placed on the right side of an expression")
        e = Expression(line_no, line, left, right)
        p.exprs.append(e)

    return p

def printable_format(line):
    assert line.startswith('^')
    assert line.endswith('$')
    return line[1:-1]

def execute(program, line, verbose=False):
    line = '^' + line.strip() + '$'
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
                    print >> sys.stderr, 'Step %d:'% operation_counter
                    print >> sys.stderr, '  L%d: %s' % (expr.line_no, expr.plain_text)
                    print >> sys.stderr, '>> %s' % printable_format(line)
                    print >> sys.stderr, '<< %s%s' % ('(return)' if executed == EXECUTED_RETURN else '', printable_format(output))
                    print >> sys.stderr, ''
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

    with open(args.filename) as input_file:
        plain_text = input_file.read()
        program = parse(plain_text)

    line = raw_input()
    result = execute(program, line, args.verbose)
    print result

