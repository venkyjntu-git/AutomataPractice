AUTOMATA DFA

template_id: DFA_BEGINS_LENGTH_K

pattern_family: {begins with}

difficulty: 0

description:
Construct a DFA that accepts all strings that begin with
S where the length of S is K.

alphabet:
    size: 2
    symbol_pools:
        {a,b,c}
        {0,1}

roles:{
    A <- alpha[0]
    B <- alpha[1]
}
parameters:
    K in [1,5]
    S in strings({A,B}, K)

condition:
    begins_with(S)  

testing:
    cases: 200
    max_length: 50

tags: {dfa,prefix}

closure_allowed: true 

END