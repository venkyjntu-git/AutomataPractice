AUTOMATA TM

template_id: TM_UNEQUAL_BLOCKS_A_B_C

pattern_family: {counting}

difficulty: 5

description:
Construct a TM accepting strings where the 
M number of A symbols followed by N number of  B symbols 
followed by P number of C symbols

alphabet:
    size: 3
    symbol_pools:{a,b,c,d,e}
                 {p,q,r,s,t}
                 {0,1,2,3,4}

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
    M != N or N !=P 
    M > 0
    N > 0

testing:
    cases: 200
    max_length: 10

tags: {TM,counting}

closure_allowed: false 

END