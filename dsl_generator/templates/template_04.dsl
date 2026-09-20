AUTOMATA DFA

template_id: DFA_BEGIN_ENDS_LENGTH_K1_K2

pattern_family: {begins with and ends with}

difficulty: 2

description:
Construct a DFA that accepts all strings that begins with S1 and ends with
a S2 where the length of S1 is K1 and length of S2 is K2.

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
    K1 in [1,5]
    K2 in [1,5]
    S1 in strings({A,B}, K1)
    S2 in strings({A,B}, K2)

condition:
    begins_with(S1) 
    ends_with(S2)  

testing:
    cases: 200
    max_length: 50

tags: {dfa,prefix}

closure_allowed: true 

END