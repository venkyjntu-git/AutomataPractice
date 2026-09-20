AUTOMATA TM

template_id: TM_N1_A_FOLLOWED_BY_N2_B

pattern_family: {counting}

difficulty: 4

description:
Construct a TM accepting strings where the K1*N number of A symbols followed by K2*N number of  B symbols.

alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
    A <- alpha[0]
    B <- alpha[1]
}

parameters:
    K1 in [1,2]
    K2 in [1,2]

condition:
    count(A) == K1*N
    count(B) == K2*N
    prefix_order(A,B)
    N > 0

testing:
    cases: 200
    max_length: 50

tags: {TM,counting}

closure_allowed: false 

END