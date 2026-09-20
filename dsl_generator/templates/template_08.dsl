
AUTOMATA DFA

template_id: DFA_LENGTH_ATLEAST_K

pattern_family: {length of string atleast k}

difficulty: 0

description:
Construct a DFA that accepts all strings where length of string is atleast K.

alphabet:
    size: 2
    symbol_pools:
        {a,b,c}
        {0,1}

roles:{
}
parameters:
    K in [2,5]
    
condition:
    length >= K 
      
testing:
    cases: 200
    max_length: 50

tags: {dfa,length of string}

closure_allowed: true 

END