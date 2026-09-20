AUTOMATA PDA

template_id: PDA_MORE_A_FOLLOWED_BY_B

pattern_family: {counting}

difficulty: 1

description:
Construct a PDA accepting strings where the 
M number of A symbols followed by N number of  B symbols and M is greater than N 

alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
    A <- alpha[0]
    B <- alpha[1]
}

parameters:

condition:
    count(A) == M 
    count(B) == N
    prefix_order(A,B)
    M > 0
    N > 0
    M > N

testing:
    cases: 200
    max_length: 50

tags: {PDA,counting}

closure_allowed: true 

END