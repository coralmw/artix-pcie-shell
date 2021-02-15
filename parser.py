GRAMMAR = '''
@@grammar::BSVInterface

start = interfaceDecl $ ;

interfaceDecl
    = 'interface' typeDefType ';'
        { interfaceMemberDecl }
    'endinterface:' typeDefType ;
    

typeDefType = string ;
interfaceMemberDecl = methodProto ;

methodProto = 'method' type identifier methodProtoFormals ';' ;
methodProtoFormals = '(' [@+:methodProtoFormal {',' @+:methodProtoFormal}* ] ')' ;

methodProtoFormal = type identifier ;

type = string [ '#' [ '(' type ')' ] ] ;
plaintype = string ;
identifier = string ;
string = /[a-zA-Z0-9\_]+/ ;
'''

INTERFACE = """
interface Ifc_type;
  method Action collatz_submit(Int#(64) n);
  method ActionValue#(Int#(64)) collatz_get();
endinterface: Ifc_type
"""

import pprint
import json
from tatsu import parse, compile
from tatsu.util import asjson

grammar = compile(GRAMMAR, name="BSVInterface")
ast = parse(grammar, INTERFACE)
pprint.pprint(ast)