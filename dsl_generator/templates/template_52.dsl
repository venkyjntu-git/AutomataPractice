AUTOMATA DFA

template_id: DFA_COUNT

pattern_family: {counting}

difficulty: 1

description:
Construct a DFA accepting strings where the number of A symbols is k.

alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
    A <- alpha[0]
}

parameters:
    k in [0,5]

condition:
    count(A) == k

testing:
    cases: 200
    max_length: 50

tags: {dfa,counting}

closure_allowed: false
END