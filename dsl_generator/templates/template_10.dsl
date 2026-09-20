
AUTOMATA DFA

template_id: DFA_LENGTH_EQUAL_TO_K

pattern_family: {length of string is equal to k}

difficulty: 0

description:
Construct a DFA that accepts all strings where length of string is equal to K.

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
    length == K 
      
testing:
    cases: 200
    max_length: 50

tags: {dfa,length of string}

closure_allowed: false 

END