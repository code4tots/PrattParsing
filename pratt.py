'''
yparse.py

'''

'''
global variables
'''

token = None
stream = None

delimiters = set()  # e.g. ; for demarcating the end of an expression
binops     = set()  # e.g. +
tenops     = dict() # e.g. ? -> :
suffix     = set()  # e.g. ++
prefix     = set()  # e.g. ++
group      = dict() # e.g. ( -> )

lbp        = dict() # left binding power
nud_rbp    = dict() # right binding power in nud
led_rbp    = dict() # right binding power in led

exptokens  = set()  # Strings explicitly declared to be valid tokens

'''
functions for setting up the global variables
'''

def register_binop(name,l,r):
    exptokens.add(name)
    binops.add(name)
    lbp[name]     = l
    led_rbp[name] = r

def register_tenop(name,closer,l,r):
    exptokens.add(name)
    exptokens.add(closer)
    tenops[name] = closer
    delimiters.add(closer)
    lbp[name] = l
    led_rbp[name] = r

def register_suffix(name,l):
    exptokens.add(name)
    suffix.add(name)
    lbp[name] = l

def register_prefix(name,r):
    exptokens.add(name)
    prefix.add(name)
    nud_rbp[name] = r

def register_group(name,closer,l):
    exptokens.add(name)
    exptokens.add(closer)
    group[name] = closer
    delimiters.add(closer)
    lbp[name] = l

def register_delimiter(name):
    exptokens.add(name)
    delimiters.add(name)

def loadops():
    '''
    Load the operator data from a specially prepared file
    In this case operatordata.txt is hardcoded, but this is not
    difficult to change.

    In fact, it isn't difficult to modify operatordata.txt to fit
    various needs
    '''

    with open('operatordata.txt') as f:
        for line in f.readlines():
            line = line.strip()
            if line == '' or line[0] == '#': continue
            st, name, closer, l, r = line.split()
            if   st == 'binop' : register_binop(name,int(l),int(r))
            elif st == 'tenop' : register_tenop(name,closer,int(l),int(r))
            elif st == 'suffix': register_suffix(name,int(l))
            elif st == 'prefix': register_prefix(name,int(r))
            elif st == 'group' : register_group(name,closer,int(l))
    register_delimiter(';')
    register_delimiter('{')
    register_delimiter('}')

def init(s):
    global token, stream
    stream = lex(s)
    token = next(stream)

'''
lex code
'''

def lex(s):
    '''
    lexes: exptokens (explicitly declared), words, int, float, string literals
    skips all whitespace
    '''
    ''' skipping leading whitespace '''
    i = next(k for k in range(len(s)+1) if k==len(s) or not s[k].isspace())

    while i < len(s):
        if any(s.startswith(t,i) for t in exptokens):
            ''' explicitly declared tokens '''
            t = next(t for t in exptokens if s.startswith(t,i))
            yield t
            i += len(t)
        elif s[i].isalpha() or s[i] == '_':
            ''' alphanumeric underscore token '''
            j = i
            i = next(k for k in range(i,len(s)+1)
                     if k==len(s) or not (s[k].isalpha() or s[k]=='_'))
            yield s[j:i]
        elif s[i].isdigit():
            ''' numeric: integer or float '''
            j = i
            i = next(k for k in range(i,len(s)+1)
                     if k==len(s) or not s[k].isdigit())
            if i < len(s) and s[i] == '.':
                ''' if we have a dot following int, it is a float '''
                i = next(k for k in range(i+1,len(s)+1)
                         if k==len(s) or not s[k].isdigit())
            yield s[j:i]
        elif s[i] == '"':
            ''' string literal '''
            j=i
            i=next(k for k in range(i+1,len(s)+1)
                   if k==len(s) or s[k] in ['"','\\'])
            while i < len(s) and s[i] == '\\':
                i=next(k for k in range(i+1,len(s)+1)
                       if k==len(s) or s[k] in ['"','\\'])
            i += 1
            yield s[j:i]
        elif not s[i].isspace():
            ''' if we hit here, we found an unrecognized token '''
            j = i
            i = next(k for k in range(i+1,len(s)+1)
                     if k==len(s) or not s[k].isspace())
            raise Exception("unrecognized token '%s'"%s[j:i])

        ''' skip whitespace '''
        i = next(k for k in range(i,len(s)+1)
                 if k==len(s) or not s[k].isspace())

    '''
    At the very end, give the stream one extra thing to chew on.
    Otherwise, we may get a StopIteration exception when trying to
    'expect' the last token.
    '''
    yield None

def next_token():
    global token
    t = token
    token = next(stream)
    return t

def expect(t):
    if not consume(t):
        raise Exception("Expected '%s' but got '%s'"%(t,token))

def consume(t):
    if t == token:
        next_token()
        return True
    return False

'''
nud, led, expression --> Pratt Parsing
'''

def nud(t):
    if t in prefix:
        return (('prefix',t),[expression(nud_rbp[t])])
    elif t in group:
        args = []
        if token != group[t]:
            # it is a little weird here because comma is a binop,
            # so it can't also be a delimiter
            args.append(expression(lbp[',']+1))
            while token != group[t]:
                expect(',')
                args.append(expression())
        expect(group[t])
        return (('nud group', t), args)
    else:
        return (('name',t),[])

def led(t,left):
    if t in binops:
        return (('binop',t),[left,expression(led_rbp[t])])
    elif t in tenops:
        middle = expression()
        expect(tenops[t])
        return (('tenop',t),[left,middle,expression(led_rbp[t])])
    elif t in suffix:
        return (('suffix',t),[left])
    elif t in group:
        args = [left]
        if token != group[t]:
            args.append(expression(lbp[',']+1))
            while token != group[t]:
                expect(',')
                args.append(expression())
        expect(group[t])
        return (('led group',t),args)

def expression(rbp=0):
    '''
    Parses expression
    Pratt's parsing algorithm

    Parsed expressions always have form
    ( (parse_type, token), list_of_subexpressions )
    '''

    left = nud(next_token())
    while token not in delimiters and rbp < lbp[token]:
        left = led(next_token(),left)
    return left

def typename():
    '''
    Parses a typename
    
    Because C/C++ typenames are EVIL...
    I made up an *almost* LL(1) variant for use here.

    ( typename_type, data, subtypenames )
    '''

    if consume('*'):
        return PointerTypename(None, [typename()])

    elif consume('['):
        args = []
        while not consume(']'):
            args.append(typename())
        return TemplateTypename(None, args)

    elif consume('('):
        args = []
        while not consume(')'):
            args.append(typename())
        return FunctionTypename(None, args)

    else:
        return NameTypename(next_token(),[])

def statement():
    '''
    Parse a statement.
    Statements are LL(1).

    Parsed statements always have form
    ( statement_type, subtypenames, subexpressions, substatements )
    '''

    if consume('return'):
        r = expression()
        expect(';')
        return ReturnStatement(r)

    elif consume('if'):
        r = expression()
        expect('{')
        ss = []
        while not consume('}'):
            ss.append(statement())
        return IfStatement(r,ss)

    elif consume('elif'):
        r = expression()
        expect('{')
        ss = []
        while not consume('}'):
            ss.append(statement())
        return ElifStatement(r,ss)

    elif consume('else'):
        expect('{')
        ss = []
        while not consume('}'):
            ss.append(statement())
        return ElseStatement(ss)

    elif consume('declare'):
        ty = typename()
        expr = []
        while True:
            expr.append(expression(lbp[',']+1))
            if not consume(','): break
        expect(';')
        return DeclareStatement(ty, expr)

    elif consume(';'):
        return PassStatement()

    else:
        r = expression()
        expect(';')
        return ExpressionStatement(r)

'''
AST for making it easy to walk the parse tree
'''

class AST(object):
    def __init__(self,data,typenames,expressions,statements):
        self.data = data
        self.typenames = typenames
        self.expressions = expressions
        self.statements = statements

    def __repr__(self):
        s = [type(self).__name__, ' ']
        if self.data:
            s.append(str(self.data))
            s.append(' ')

        if self.typenames:
            s.append('[')
            for x in map(str,self.typenames):
                s.append(x)
                s.append(', ')
            if s[-1] == ', ': s.pop()
            s.append(']')

        if self.expressions:
            s.append('[')
            for x in map(str,self.expressions):
                s.append(x)
                s.append(', ')
            if s[-1] == ', ': s.pop()
            s.append(']')

        if self.statements:
            s.append('[')
            for x in map(str,self.statements):
                s.append(x)
                s.append(', ')
            if s[-1] == ', ': s.pop()
            s.append(']')
        if s[-1] == ' ': s.pop()
        return ''.join(s)

class Typename(AST):
    def __init__(self,data,subtypenames):
        super().__init__(data,subtypenames,[],[])

class PointerTypename(Typename):
    def __repr__(self):
        return '*'+str(self.typenames[0])
class NameTypename(Typename):
    def __repr__(self):
        return self.data
class TemplateTypename(Typename):
    def __repr__(self):
        return r'%s[%s]'%(self.typenames[0],','.join(map(repr,self.typenames[1:])))
class FunctionTypename(Typename):
    def __repr__(self):
        return r'\%s->(%s)'%(self.typenames[0],','.join(map(repr,self.typenames[1:])))

class Statement(AST):
    def __init__(self,subtypenames,subexpressions,substatements):
        super().__init__(None,subtypenames,subexpressions,substatements)
    
class ReturnStatement(Statement):
    def __init__(self,returnexpression):
        super().__init__([],[returnexpression],[])

class IfTypeStatement(Statement): pass

class IfStatement(IfTypeStatement):
    def __init__(self,condition,statements):
        super().__init__([],[condition],statements)

class ElifStatement(IfStatement):
    def __init__(self,condition,statements):
        super().__init__([],[condition],statements)
    
class ElseStatement(Statement):
    def __init__(self,statements):
        super().__init__([],[],statements)

class DeclareStatement(Statement):
    def __init__(self,ty,expressions):
        super().__init__([ty],expressions,[])

class ExpressionStatement(Statement):
    def __init__(self,expr):
        super().__init__([],[expr],[])

class PassStatement(Statement):
    def __init__(self):
        super().__init__([],[],[])

    def __repr__(self):
        return 'pass'

class Expression(AST):
    def __init__(self,data,subexpressions):
        super().__init__(data,[],subexpressions,[])

class Binop(Expression):
    pass

loadops()
init('''
if a = 2 {
  declare (int [int int]) x = 2, y;
  return f(1,2,3);
}

''')
s = statement()
print(s)
