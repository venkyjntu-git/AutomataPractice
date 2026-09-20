AUTOMATA PDA

template_id: PDA_N1_A_FOLLOWED_BY_N2_B_2

pattern_family: {counting}

difficulty: 5

description:
Construct a PDA accepting strings where the K1*N number of A symbols followed by K2*N number of B symbols.

alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
    A <- alpha[0]
    B <- alpha[1]
}

parameters:
    K1 in [2,5]
    K2 in [2,5]

condition:
    count(A) == K1*N
    count(B) == K2*N
    prefix_order(A,B)
    N > 0

testing:
    cases: 200
    max_length: 50

tags: {PDA,counting}

closure_allowed: false 

END