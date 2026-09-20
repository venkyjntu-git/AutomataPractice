
AUTOMATA DFA

template_id: DFA_EVERY_A_FOLLOWED_B

pattern_family: {every symbol followed other symbol}

difficulty: 2

description:
Construct a DFA that accepts all strings where every A must be followed by B.

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
    
condition:
    every(A) followed_by(B)
      
testing:
    cases: 200
    max_length: 50

tags: {dfa,prefix}

closure_allowed: true 

END