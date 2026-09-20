AUTOMATA DFA

template_id: DFA_DECIMAL_EQUIVALENT_MOD_COUNT

pattern_family: {counting}

difficulty: 1

description:
Construct a DFA accepting binary strings whose decimal equivalent is divisible by k.

alphabet:
    size: 2
    symbol_pools:{0,1}

roles:{
}

parameters:
    k in [2,6]

condition:
    decimal_equivalent % k == 0

testing:
    cases: 200
    max_length: 50

tags: {dfa,counting}
closure_allowed: true 
END