AUTOMATA DFA
#contributed by phani srinivas pola 
template_id: DFA_SAME_START_END

pattern_family: {strings}

difficulty: 2

description:
Construct a DFA accepting strings that start and end with the same symbol S.

alphabet:
    size: 2
    symbol_pools: {a,b,c,d}
                {0,1}

roles:{
    A <- alpha[0]
    B <- alpha[1]
}
parameters:
    S in strings({A,B}, 1)

condition:
    begins_with(S) 
    ends_with(S)  

testing:
    cases: 200
    max_length: 50

tags: {DFA,prefix_suffix}

closure_allowed: true
END