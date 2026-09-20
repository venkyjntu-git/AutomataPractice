AUTOMATA DFA

template_id: DFA_MOD_COUNT_A_B

pattern_family: {counting closure}

difficulty: 2

description:
Construct a DFA accepting strings where the number of A symbols is divisible by K1.
and the number of B symbols is divisible by K2.

alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
    A <- alpha[0]
    B <- alpha[1]
}

parameters:
    K1 in [2,6]
    K2 in [2,6]

condition:
    count(A) % K1 == 0
    count(B) % K2 == 0

testing:
    cases: 200
    max_length: 50

tags: {dfa,counting}

closure_allowed: true 

END