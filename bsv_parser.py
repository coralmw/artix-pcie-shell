from tatsu.model import ModelBuilderSemantics
import pprint
import json
from tatsu import parse, compile, to_python_model
from tatsu.util import asjson

class BSVInterface():

    GRAMMAR = '''
    @@grammar::BSVInterface
    @@parseinfo :: True

    start = interfaceDecl $ ;

    interfaceDecl::IFACE
        = 'interface' typeDefType ';'
            methods:{ methodProto }
        'endinterface:' typeDefType ;


    typeDefType = string ;
    interfaceMemberDecl = methodProto ;

    methodProto::METHOD = 'method' type:type name:identifier '(' params:','.{ methodProtoFormal }* ')' ';' ;

    methodProtoFormal = type:type name:identifier ;

    type::TYPE = name:string [ '#' ~ '(' arg:type ')' ] ;
    plaintype = string ;
    identifier = string ;
    string = /[a-zA-Z0-9\_]+/ ;
    '''

    def __init__(self, interface_str):
        self.parser = compile(self.GRAMMAR, name="BSVInterface", semantics=ModelBuilderSemantics())
        self.interface = interface = self.parser.parse(interface_str)

        self.actionmethods = actionmethods = []
        self.actionvaluemethods = actionvaluemethods = []


        for method in interface.methods:
            if method.type.name == 'Action':
                assert(len(method.params) == 1) # can't do multiple args here yet
                param_0_type = method.params[0].type.name
                param_0_width = int(method.params[0].type.arg.name)
                param_0_name = method.params[0].name
                method_name = method.name
                actionmethods.append( (param_0_type, param_0_width, param_0_name, method_name) )
            elif method.type.name == 'ActionValue':
                ret_type = method.type.arg
                type = ret_type.name
                width = int(ret_type.arg.name) # we only support Int
                method_name = method.name
                actionvaluemethods.append( (type, width, method_name) )
            else:
                print("method type", method.type.name, "of method", method.name, "not supported!")
