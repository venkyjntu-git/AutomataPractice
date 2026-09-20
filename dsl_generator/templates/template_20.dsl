AUTOMATA TM

template_id: TM_N_A_FOLLOWED_BY_B

pattern_family: {counting}

difficulty: 2

description:
Construct a TM accepting strings where the 
K*N number of A symbols followed by N number of  B symbols.

alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
    A <- alpha[0]
    B <- alpha[1]
}

parameters:
    K in [1,2]

condition:
    count(A) == K*N
    count(B) == N
    prefix_order(A,B)
    N > 0

testing:
    cases: 200
    max_length: 50

tags: {TM,counting}

closure_allowed: true
END