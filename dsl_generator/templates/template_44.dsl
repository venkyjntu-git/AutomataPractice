AUTOMATA PDA

template_id: PDA_LINEAR_1

pattern_family: {linear}

difficulty: 3

description:
Construct a PDA accepting strings where the string has 
N number of A symbols and M number of B symbols where N = M+2

alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
    A <- alpha[0]
    B <- alpha[1]
}

parameters:

condition:
    count(A) == N
    count(B) == M
    N = M + 2
    N>0
    M>0

testing:
    cases: 200
    max_length: 50

tags: {PDA,linear}

closure_allowed: true
END