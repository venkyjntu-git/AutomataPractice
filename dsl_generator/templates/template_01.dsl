AUTOMATA DFA

template_id: DFA_MOD_COUNT

pattern_family: {counting}

difficulty: 1

description:
Construct a DFA accepting strings where the number of A symbols is divisible by k.

alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
    A <- alpha[0]
}

parameters:
    k in [2,6]

condition:
    count(A) % k == 0

testing:
    cases: 200
    max_length: 50

tags: {dfa,counting}

closure_allowed: true

END