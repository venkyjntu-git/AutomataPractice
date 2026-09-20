AUTOMATA PDA

template_id: PDA_PALINDROME

pattern_family: {palindromes}

difficulty: 5

description:
Design a nondeterministic PDA that accepts all 
palindromes over the given alphabet strings that read the same
forwards and backwards.  Both even-length and odd-length
palindromes must be accepted.


alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
}

parameters:

condition: palindrome

testing:
    cases: 200
    max_length: 50

tags : { PDA, palindrome, nondeterminism, CFG, non_DPDA, advanced }

closure_allowed: false 

END