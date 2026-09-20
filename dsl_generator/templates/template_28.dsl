AUTOMATA TM

template_id: TM_N1_A_FOLLOWED_BY_N2_B_FOLLOWED_BY_N3_C_5

pattern_family: {counting}

difficulty: 5

description:
Construct a TM accepting strings where the K*N number of A symbols 
followed by N number of B symbols 
followed by K*N number of C symbols

alphabet:
    size: 3
    symbol_pools:{a,b,c,d}
                 {0,1,2}

roles:{
    A <- alpha[0]
    B <- alpha[1]
    C <- alpha[2]
}

parameters:
    K in [1,3]

condition:
    count(A) == K*N
    count(B) == N
    count(C) == K*N
    prefix_order(A,B,C)
    N > 0

testing:
    cases: 200
    max_length: 50

tags: {TM,counting}

closure_allowed: false

END