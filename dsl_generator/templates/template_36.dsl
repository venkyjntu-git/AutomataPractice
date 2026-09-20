AUTOMATA PDA

template_id: PDA_A_FOLLOWED_BY_B_FOLLOWED_BY_C

pattern_family: {counting}

difficulty: 2

description:
Construct a PDA accepting strings where the 
M number of A symbols followed by N number of  B symbols 
followed by (M+N) number of C symbols

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

condition:
    count(A) == M 
    count(B) == N
    count(C) == (M+N)
    prefix_order(A,B,C)
    M > 0
    N > 0

testing:
    cases: 200
    max_length: 10

tags: {PDA,counting}

closure_allowed: true 

END