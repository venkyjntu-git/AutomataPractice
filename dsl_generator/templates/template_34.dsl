AUTOMATA TM

template_id: TM_N1_A_FOLLOWED_BY_N2_B_FOLLOWED_BY_N3_C_9

pattern_family: {counting}

difficulty: 5

description:
Construct a TM accepting strings where the M number of A symbols 
followed by N number of B symbols 
followed by P number of C symbols

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
    count(C) == P
    prefix_order(A,B,C)
    M > 0
    N > 0
    P > 0
    M < N 
    M < P

testing:
    cases: 200
    max_length: 50

tags: {TM,counting}

closure_allowed: false 

END