AUTOMATA TM

template_id: TM_EQUAL_A_B_C

pattern_family: {counting}

difficulty: 4

description:
Construct a TM accepting strings where the string has 
equal number of A symbols, equal number of B symbols,
equal number of C symbols      
alphabet:
    size: 3
    symbol_pools:{a,b,c,d}
                 {0,1,2,3}

roles:{
    A <- alpha[0]
    B <- alpha[1]
    C <- alpha[2]
}

parameters:

condition:
    count(A) == count(B)
    count(B) == count(C) 

testing:
    cases: 200
    max_length: 50

tags: {TM,counting}

closure_allowed: true 

END