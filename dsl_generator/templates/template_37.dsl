AUTOMATA TM

template_id: TM_A_FOLLOWED_BY_B_FOLLOWED_BY_C_1

pattern_family: {counting}

difficulty: 4

description:
Construct a TM accepting strings where the 
M number of A symbols followed by N number of  B symbols 
followed by more than (M+N) number of C symbols

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
    count(C) > (M+N)
    prefix_order(A,B,C)
    M > 0
    N > 0

testing:
    cases: 200
    max_length: 10

tags: {TM,counting}

closure_allowed: true

END