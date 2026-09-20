AUTOMATA PDA

template_id: PDA_BALANCE_PARAN

pattern_family: {balanced paranthesis}

difficulty: 4

description:
Construct a PDA accepting strings where the string has equal number of A symbols and equal number of B symbols, 
prefix_count(A) is greater than equal to prefix_count(B) 
alphabet:
    size: 2
    symbol_pools: {(,)}
                 {[,]}

roles:{
    A <- alpha[0]
    B <- alpha[1]
}

parameters:

condition:
    count(A) == count(B)
    prefix_count(A) >= prefix_count(B)

testing:
    cases: 200
    max_length: 50

tags: {PDA,balanced,paranthesis}

closure_allowed: false
END