AUTOMATA PDA

template_id: PDA_EQUAL_A_B

pattern_family: {counting}

difficulty: 2

description:
Construct a PDA accepting strings where the string has 
equal number of A symbols and equal number of B symbols    
alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}
                 {(,)}
                 {[,]}

roles:{
    A <- alpha[0]
    B <- alpha[1]
}

parameters:

condition:
    count(A) == count(B)
     

testing:
    cases: 200
    max_length: 50

tags: {PDA,counting}

closure_allowed: true 
END