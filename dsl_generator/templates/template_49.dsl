AUTOMATA TM

template_id: TM_N1_A_FOLLOWED_BY_N2_B_FOLLOWED_BY_N3_C_FOLLOWED_BY_N4_D

pattern_family: {counting}

difficulty: 4

description:
Construct a TM accepting strings where the N number of A symbols 
followed by N number of B symbols 
followed by N number of C symbols
followed by N number of D symbols

alphabet:
    size: 4
    symbol_pools:{a,b,c,d}
                 {0,1,2,3}

roles:{
    A <- alpha[0]
    B <- alpha[1]
    C <- alpha[2]
    D <- alpha[3]
}

parameters:

condition:
    count(A) == N
    count(B) == N
    count(C) == N
    count(D) == N
    prefix_order(A,B,C,D)
    N > 0

testing:
    cases: 200
    max_length: 50

tags: {TM,counting}

closure_allowed: false

END