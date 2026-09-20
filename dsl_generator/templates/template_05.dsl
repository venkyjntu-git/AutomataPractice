AUTOMATA DFA

template_id: DFA_CONTAINS_LENGTH_K

pattern_family: {contains}

difficulty: 2

description:
Construct a DFA that accepts all strings cotaining substring S where the length of S is K.

alphabet:
    size: 2
    symbol_pools:
        {a,b,c}
        {0,1}

roles: {
    A <- alpha[0]
    B <- alpha[1]
}
parameters:
    K in [2,5]
    S in strings({A,B}, K)

condition:
    contains(S) 

testing:
    cases: 200
    max_length: 50

tags: {dfa,contains}

closure_allowed: true 

END