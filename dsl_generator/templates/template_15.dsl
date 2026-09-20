AUTOMATA PDA

template_id: PDA_N_A_FOLLOWED_BY_B_2

pattern_family: {counting}

difficulty: 3

description:
Construct a PDA accepting strings where the 
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
    K in [3,5]

condition:
    count(A) == K*N
    count(B) == N
    prefix_order(A,B)
    N > 0

testing:
    cases: 200
    max_length: 50

tags: {PDA,counting}

closure_allowed: true 

END