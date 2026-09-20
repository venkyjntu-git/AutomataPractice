AUTOMATA DFA

template_id: DFA_NO_ADJACENT_SAME

pattern_family: {adjacency}

difficulty: 1

description:
Construct a DFA accepting strings where no two adjacent symbols are the same.

alphabet:
    size: 2
    symbol_pools:
        {a,b,c}
        {0,1}

roles:{
}

condition:
    no_adjacent_same

testing:
    cases: 200
    max_length: 50

tags: {dfa,adjacency}

closure_allowed: true

END
